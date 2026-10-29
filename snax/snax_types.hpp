/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// The integer types and the per-lane arithmetic every SNAX datapath runs
// (snax_datapath.hpp) and the tests check, moved here unchanged from
// snax_unit.hpp: NumPy's arithmetic on integer types (SnaxUnitType: 8 to 64
// bits, signed or not), each port with its own (PACK0). A port of W lanes of b
// bits takes W * b / 64 channel words, lane l at bits [l * b, (l + 1) * b) of
// them side by side (the wire slice). An elementwise op runs per lane at T,
// the result type of its two inputs' types (snax_unit_result_type; none for a
// signed type with uint64), each operand extended to T by its own signedness;
// the result wraps at T and is cast to the output's type (its low bits, or
// extended by T's signedness). A fold casts each lane from the input's type to
// the output's, and runs its tree and acc at the output's type; its output beat
// is one word. min and max compare by the signedness of the type they run at.
// Plain C++, no GVSoC types.

#pragma once

#include <cstdint>
#include <string>
#include <vector>


// ElementwiseOp's encodings (snax-forge hw/chisel/.../elementwise/ElementwiseOp.scala)
enum SnaxUnitOp { UNIT_ADD, UNIT_SUB, UNIT_MUL, UNIT_AND, UNIT_OR, UNIT_XOR, UNIT_MIN, UNIT_MAX,
    UNIT_NB_OPS };

static const char *const snax_unit_op_names[UNIT_NB_OPS] =
    {"add", "sub", "mul", "and", "or", "xor", "min", "max"};


// An element's type: width 8, 16, 32 or 64 bits, and its signedness. A value
// of a type is held in the low width bits of a uint64_t, zeros above.
struct SnaxUnitType
{
    int width;
    bool is_signed;
};

// NumPy's name of a type: int32, uint8, ...
inline std::string snax_unit_type_name(SnaxUnitType t)
{
    return (t.is_signed ? "int" : "uint") + std::to_string(t.width);
}

inline uint64_t snax_unit_mask(int width)
{
    return width >= 64 ? ~(uint64_t)0 : ((uint64_t)1 << width) - 1;
}


// NumPy's result type of two integer types (np.result_type): the wider of
// two of the same signedness; of a signed and an unsigned one, the signed one
// when it is wider, else signed at twice the unsigned width. False when that
// is past 64 bits (a signed type with uint64: NumPy gives float64), and *t
// is then int64.
inline bool snax_unit_result_type(SnaxUnitType a, SnaxUnitType b, SnaxUnitType *t)
{
    if (a.is_signed == b.is_signed)
    {
        *t = {a.width > b.width ? a.width : b.width, a.is_signed};
        return true;
    }
    SnaxUnitType s = a.is_signed ? a : b;
    SnaxUnitType u = a.is_signed ? b : a;
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
inline uint64_t snax_unit_cast(uint64_t v, SnaxUnitType s, SnaxUnitType t)
{
    v &= snax_unit_mask(s.width);
    if (s.is_signed && s.width < 64 && (v >> (s.width - 1)) & 1)
    {
        v |= ~snax_unit_mask(s.width);
    }
    return v & snax_unit_mask(t.width);
}


// One lane of ElementwiseAlu: a op b at type t, wrapping; min and max
// compare by t's signedness. The operands are cut to t's width first.
inline uint64_t snax_unit_compute(int op, SnaxUnitType t, uint64_t a, uint64_t b)
{
    uint64_t mask = snax_unit_mask(t.width);
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
        case UNIT_ADD: r = a + b; break;
        case UNIT_SUB: r = a - b; break;
        case UNIT_MUL: r = a * b; break;
        case UNIT_AND: r = a & b; break;
        case UNIT_OR:  r = a | b; break;
        case UNIT_XOR: r = a ^ b; break;
        case UNIT_MIN: r = a_less ? a : b; break;
        default:       r = a_less ? b : a; break;  // UNIT_MAX
    }
    return r & mask;
}


// A fold's tree (snax-forge's TreeAccumulate): the n lanes of a
// beat, already of type t, reduced to one by op at t, halves first, so for n
// a power of two the pairs of Chisel's reduceTree. One lane gives that lane.
inline uint64_t snax_unit_tree(int op, SnaxUnitType t, const uint64_t *lanes, int n)
{
    if (n == 1)
    {
        return lanes[0] & snax_unit_mask(t.width);
    }
    int half = n / 2;
    return snax_unit_compute(op, t, snax_unit_tree(op, t, lanes, half),
        snax_unit_tree(op, t, lanes + half, n - half));
}


// Lane l of a beat of width-bit elements: bits [l * width, (l + 1) * width)
// of its 64-bit channel words side by side, word 0 lowest (the wire slice).
// A width of 8 to 64 divides 64, so a lane never straddles two words.
inline uint64_t snax_unit_lane(const uint64_t *words, int width, int lane)
{
    return (words[lane * width / 64] >> (lane * width % 64)) & snax_unit_mask(width);
}

inline void snax_unit_set_lane(uint64_t *words, int width, int lane, uint64_t v)
{
    words[lane * width / 64] |= (v & snax_unit_mask(width)) << (lane * width % 64);
}


// An elementwise beat, as NumPy's out = (a op b).astype(out_t): per lane, a
// and b each at its own port's type, both extended to T, their result type
// (snax_unit_result_type, which must give one), the op at T, and the result
// cast to out_t. The words: lanes * width / 64 per port, out's cleared here.
inline void snax_unit_elementwise(int op, int lanes, SnaxUnitType a_t, SnaxUnitType b_t,
    SnaxUnitType out_t, const uint64_t *a, const uint64_t *b, uint64_t *out)
{
    SnaxUnitType t;
    snax_unit_result_type(a_t, b_t, &t);
    for (int w = 0; w < lanes * out_t.width / 64; w++)
    {
        out[w] = 0;
    }
    for (int lane = 0; lane < lanes; lane++)
    {
        uint64_t x = snax_unit_cast(snax_unit_lane(a, a_t.width, lane), a_t, t);
        uint64_t y = snax_unit_cast(snax_unit_lane(b, b_t.width, lane), b_t, t);
        snax_unit_set_lane(out, out_t.width, lane,
            snax_unit_cast(snax_unit_compute(op, t, x, y), t, out_t));
    }
}


// A fold's firing: the beat's lanes, each cast from in_t to out_t, through
// the tree at out_t; the first firing of an output starts its value with
// that, the others fold it in, op(acc, x) at out_t. Returns the output's
// value so far: its one word, the element in the low out_t.width bits.
inline uint64_t snax_unit_fold(int op, int lanes, SnaxUnitType in_t, SnaxUnitType out_t,
    const uint64_t *in, bool first, uint64_t acc)
{
    std::vector<uint64_t> x(lanes);
    for (int lane = 0; lane < lanes; lane++)
    {
        x[lane] = snax_unit_cast(snax_unit_lane(in, in_t.width, lane), in_t, out_t);
    }
    uint64_t sum = snax_unit_tree(op, out_t, x.data(), lanes);
    return first ? sum : snax_unit_compute(op, out_t, acc, sum);
}
