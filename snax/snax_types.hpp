/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// The integer types and the per-lane arithmetic every SNAX datapath runs
// (snax_datapath.hpp) and the tests check: NumPy's arithmetic on integer types
// (SnaxType: 8 to 64 bits, signed or not), each port with its own. A port of W
// lanes of b bits takes W * b / 64 channel words, lane l at bits
// [l * b, (l + 1) * b) of them side by side (the wire slice). An elementwise
// op runs per lane at T, the result type of its two inputs' types
// (snax_op_result_type; none for a signed type with uint64), each operand
// extended to T by its own signedness; the result wraps at T and is cast to
// the output's type (its low bits, or extended by T's signedness). A fold
// casts each lane from the input's type to the output's, and runs its tree and
// acc at the output's type; its output beat is one word. min and max compare
// by the signedness of the type they run at. Plain C++, no GVSoC types.

#pragma once

#include <cstdint>
#include <string>
#include <vector>


// ElementwiseOp's encodings (snax-forge hw/chisel/.../elementwise/ElementwiseOp.scala)
enum SnaxOp { SNAX_OP_ADD, SNAX_OP_SUB, SNAX_OP_MUL, SNAX_OP_AND, SNAX_OP_OR, SNAX_OP_XOR,
    SNAX_OP_MIN, SNAX_OP_MAX, SNAX_NB_OPS };

static const char *const snax_op_names[SNAX_NB_OPS] =
    {"add", "sub", "mul", "and", "or", "xor", "min", "max"};


// An element's type: width 8, 16, 32 or 64 bits, and its signedness. A value
// of a type is held in the low width bits of a uint64_t, zeros above.
struct SnaxType
{
    int width;
    bool is_signed;
};

// NumPy's name of a type: int32, uint8, ...
inline std::string snax_type_name(SnaxType t)
{
    return (t.is_signed ? "int" : "uint") + std::to_string(t.width);
}

inline uint64_t snax_lane_mask(int width)
{
    return width >= 64 ? ~(uint64_t)0 : ((uint64_t)1 << width) - 1;
}


// NumPy's result type of two integer types (np.result_type): the wider of
// two of the same signedness; of a signed and an unsigned one, the signed one
// when it is wider, else signed at twice the unsigned width. False when that
// is past 64 bits (a signed type with uint64: NumPy gives float64), and *t
// is then int64.
inline bool snax_op_result_type(SnaxType a, SnaxType b, SnaxType *t)
{
    if (a.is_signed == b.is_signed)
    {
        *t = {a.width > b.width ? a.width : b.width, a.is_signed};
        return true;
    }
    SnaxType s = a.is_signed ? a : b;
    SnaxType u = a.is_signed ? b : a;
    if (s.width > u.width)
    {
        *t = s;
        return true;
    }
    *t = {2 * u.width > 64 ? 64 : 2 * u.width, true};
    return 2 * u.width <= 64;
}


// A value of type s as type t: sign- or zero-extended by s's signedness when
// t is wider, its low t.width bits when t is narrower (NumPy's astype)
inline uint64_t snax_lane_cast(uint64_t v, SnaxType s, SnaxType t)
{
    v &= snax_lane_mask(s.width);
    if (s.is_signed && s.width < 64 && (v >> (s.width - 1)) & 1)
    {
        v |= ~snax_lane_mask(s.width);
    }
    return v & snax_lane_mask(t.width);
}


// One lane of ElementwiseAlu: a op b at type t, wrapping; min and max
// compare by t's signedness. The operands are cut to t's width first.
inline uint64_t snax_op_compute(int op, SnaxType t, uint64_t a, uint64_t b)
{
    uint64_t mask = snax_lane_mask(t.width);
    a &= mask;
    b &= mask;
    bool a_less = a < b;
    if (t.is_signed)
    {
        // Sign-extend to 64 bits, then compare
        int shift = 64 - t.width;
        a_less = ((int64_t)(a << shift) >> shift) < ((int64_t)(b << shift) >> shift);
    }
    uint64_t r;
    switch (op)
    {
        case SNAX_OP_ADD: r = a + b; break;
        case SNAX_OP_SUB: r = a - b; break;
        case SNAX_OP_MUL: r = a * b; break;
        case SNAX_OP_AND: r = a & b; break;
        case SNAX_OP_OR:  r = a | b; break;
        case SNAX_OP_XOR: r = a ^ b; break;
        case SNAX_OP_MIN: r = a_less ? a : b; break;
        default:       r = a_less ? b : a; break;  // SNAX_OP_MAX
    }
    return r & mask;
}


// A fold's tree (snax-forge's TreeAccumulate): the n lanes of a
// beat, already of type t, reduced to one by op at t, halves first, so for n
// a power of two the pairs of Chisel's reduceTree. One lane gives that lane.
inline uint64_t snax_op_tree(int op, SnaxType t, const uint64_t *lanes, int n)
{
    if (n == 1)
    {
        return lanes[0] & snax_lane_mask(t.width);
    }
    int half = n / 2;
    return snax_op_compute(op, t, snax_op_tree(op, t, lanes, half),
        snax_op_tree(op, t, lanes + half, n - half));
}


// Lane l of a beat of width-bit elements: bits [l * width, (l + 1) * width)
// of its 64-bit channel words side by side, word 0 lowest (the wire slice).
// A width of 8 to 64 divides 64, so a lane never straddles two words.
inline uint64_t snax_lane_get(const uint64_t *words, int width, int lane)
{
    return (words[lane * width / 64] >> (lane * width % 64)) & snax_lane_mask(width);
}

inline void snax_lane_set(uint64_t *words, int width, int lane, uint64_t v)
{
    words[lane * width / 64] |= (v & snax_lane_mask(width)) << (lane * width % 64);
}


// An elementwise beat, as NumPy's out = (a op b).astype(out_t): per lane, a
// and b each at its own port's type, both extended to T, their result type
// (snax_op_result_type, which must give one), the op at T, and the result
// cast to out_t. The words: lanes * width / 64 per port, out's cleared here.
inline void snax_op_elementwise(int op, int lanes, SnaxType a_t, SnaxType b_t,
    SnaxType out_t, const uint64_t *a, const uint64_t *b, uint64_t *out)
{
    SnaxType t;
    snax_op_result_type(a_t, b_t, &t);
    for (int w = 0; w < lanes * out_t.width / 64; w++)
    {
        out[w] = 0;
    }
    for (int lane = 0; lane < lanes; lane++)
    {
        uint64_t x = snax_lane_cast(snax_lane_get(a, a_t.width, lane), a_t, t);
        uint64_t y = snax_lane_cast(snax_lane_get(b, b_t.width, lane), b_t, t);
        snax_lane_set(out, out_t.width, lane,
            snax_lane_cast(snax_op_compute(op, t, x, y), t, out_t));
    }
}


// A fold's firing: the beat's lanes, each cast from in_t to out_t, through
// the tree at out_t; the first firing of an output starts its value with
// that, the others fold it in, op(acc, x) at out_t. Returns the output's
// value so far: its one word, the element in the low out_t.width bits.
inline uint64_t snax_op_fold(int op, int lanes, SnaxType in_t, SnaxType out_t,
    const uint64_t *in, bool first, uint64_t acc)
{
    std::vector<uint64_t> x(lanes);
    for (int lane = 0; lane < lanes; lane++)
    {
        x[lane] = snax_lane_cast(snax_lane_get(in, in_t.width, lane), in_t, out_t);
    }
    uint64_t sum = snax_op_tree(op, out_t, x.data(), lanes);
    return first ? sum : snax_op_compute(op, out_t, acc, sum);
}
