// Portable fixed-tone NCO. See docs/nco-rtl.md for the clock/numerical contract.
// LUT_ADDR_WIDTH is supported from 2 through 12 (default: 1024 sine samples).
module rf_nco #(
    parameter integer LUT_ADDR_WIDTH = 10,
    parameter integer PHASE_WIDTH = 32,
    parameter integer OUTPUT_WIDTH = 14
) (
    input  logic               clk,
    input  logic               rst,
    input  logic               enable,
    input  logic [PHASE_WIDTH-1:0] phase_increment,
    output logic signed [OUTPUT_WIDTH-1:0] i_out,
    output logic signed [OUTPUT_WIDTH-1:0] q_out,
    output logic               sample_valid
);
    localparam integer LUT_DEPTH = 1 << LUT_ADDR_WIDTH;
    localparam logic [LUT_ADDR_WIDTH-1:0] QUARTER_CYCLE =
        LUT_ADDR_WIDTH'(1 << (LUT_ADDR_WIDTH - 2));

    logic [PHASE_WIDTH-1:0] phase;
    logic [LUT_ADDR_WIDTH-1:0] q_address;
    logic [LUT_ADDR_WIDTH-1:0] i_address;
    logic signed [OUTPUT_WIDTH-1:0] sine_lut [0:LUT_DEPTH-1];

    `include "sine_lut_12b.svh"

    // Constant evaluation ONLY: no multiplier or shifter is used at runtime.
    // Q2.46 normalized sine times the symmetric full scale fits signed 64 bits
    // for OUTPUT_WIDTH <= 16. Round magnitude to nearest, ties away from zero.
    function automatic logic signed [OUTPUT_WIDTH-1:0] quantize_lut(
        input logic signed [47:0] normalized
    );
        logic signed [63:0] scaled;
        scaled = 64'(normalized) * ((64'sd1 << (OUTPUT_WIDTH - 1)) - 64'sd1);
        if (scaled >= 64'sd0)
            quantize_lut = OUTPUT_WIDTH'((scaled + (64'sd1 << 45)) >>> 46);
        else
            quantize_lut = OUTPUT_WIDTH'(-((-scaled + (64'sd1 << 45)) >>> 46));
    endfunction

    generate
        if (LUT_ADDR_WIDTH < 2 || LUT_ADDR_WIDTH > 12) begin : invalid_lut_width
            initial $fatal(1, "LUT_ADDR_WIDTH must be in [2, 12]");
        end
        if (PHASE_WIDTH < LUT_ADDR_WIDTH || PHASE_WIDTH > 64) begin : invalid_phase_width
            initial $fatal(1, "PHASE_WIDTH must be in [LUT_ADDR_WIDTH, 64]");
        end
        if (OUTPUT_WIDTH < 2 || OUTPUT_WIDTH > 16) begin : invalid_output_width
            initial $fatal(1, "OUTPUT_WIDTH must be in [2, 16]");
        end
    endgenerate

    // Every initialization value is an elaboration-time integer constant.
    // Subsampling the master grid gives exactly 2**LUT_ADDR_WIDTH ROM words.
    initial begin
        for (integer index = 0; index < LUT_DEPTH; index = index + 1) begin
            sine_lut[index] = quantize_lut(sine_lut_constant(12'(index << (12 - LUT_ADDR_WIDTH))));
        end
    end

    // Explicitly discard low phase bits for lookup only; retain them in phase.
    assign q_address = phase[PHASE_WIDTH-1 -: LUT_ADDR_WIDTH];
    // Explicit modulo-2**LUT_ADDR_WIDTH address addition for cos = sin(+pi/2).
    assign i_address = LUT_ADDR_WIDTH'(q_address + QUARTER_CYCLE);

    always_ff @(posedge clk) begin
        if (rst) begin
            phase        <= '0;
            i_out        <= '0;
            q_out        <= '0;
            sample_valid <= 1'b0;
        end else begin
            sample_valid <= enable;
            if (enable) begin
                i_out <= sine_lut[i_address];
                q_out <= sine_lut[q_address];
                // Explicit modulo-2**PHASE_WIDTH wrap; no saturation or phase reset.
                phase <= PHASE_WIDTH'(phase + phase_increment);
            end
        end
    end
endmodule
