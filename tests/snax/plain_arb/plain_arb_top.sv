// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// rr_arb_tree as stream_xbar instantiates it in snitch_tcdm_interconnect.sv
// (ExtPrio 0, AxiVldRdy 1, LockIn 1, FairArb by default 1), with one-bit data,
// for the winner check (README.md).
module plain_arb_top #(
  parameter int unsigned NumIn = 15
) (
  input  logic                       clk_i,
  input  logic                       rst_ni,
  input  logic [NumIn-1:0]           req_i,
  output logic [NumIn-1:0]           gnt_o,
  output logic                       req_o,
  input  logic                       gnt_i,
  output logic [$clog2(NumIn)-1:0]   idx_o
);
  logic [NumIn-1:0] data;
  assign data = '0;

  rr_arb_tree #(
    .NumIn     ( NumIn ),
    .DataWidth ( 1     ),
    .ExtPrio   ( 1'b0  ),
    .AxiVldRdy ( 1'b1  ),
    .LockIn    ( 1'b1  ),
    .FairArb   ( 1'b1  )
  ) i_arb (
    .clk_i,
    .rst_ni,
    .flush_i ( 1'b0  ),
    .rr_i    ( '0    ),
    .req_i,
    .gnt_o,
    .data_i  ( data  ),
    .req_o,
    .gnt_i,
    .data_o  (       ),
    .idx_o
  );
endmodule
