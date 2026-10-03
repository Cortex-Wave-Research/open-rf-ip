// Equivalent constant-config chirp timing harness; no external streaming pins.
module chirp_mode_top #(parameter integer HIGH_PURITY=0) (
    input logic clk,
    output logic activity
);
    localparam integer P=(HIGH_PURITY != 0) ? 64 : 32;
    localparam integer B=(HIGH_PURITY != 0) ? 18 : 14;
    localparam logic [P-1:0] START=(HIGH_PURITY != 0) ? P'(64'd368934881474191032) : P'(32'd85899346);
    localparam logic signed [P-1:0] STEP=(HIGH_PURITY != 0) ? P'(64'sd332074600786851) : P'(32'sd77317);
    logic [3:0] startup=4'b1111;
    logic signed [B-1:0] i_sample,q_sample;
    logic valid,first,last,unused_busy;
    logic [P-1:0] unused_word;
    logic [31:0] unused_count;
    always_ff @(posedge clk) startup <= {startup[2:0],1'b0};
    rf_chirp_nco_mode #(.HIGH_PURITY(HIGH_PURITY)) chirp (
        .clk(clk),.rst(startup[3]),.enable(1'b1),.start(1'b1),.start_phase_inc(START),
        .chirp_step(STEP),.chirp_length(32'd10000),.repeat_mode(1'b1),
        .i_out(i_sample),.q_out(q_sample),.sample_valid(valid),.chirp_start(first),
        .chirp_end(last),.busy(unused_busy),.phase_increment(unused_word),.chirp_count(unused_count));
    always_ff @(posedge clk)
        if (startup[3]) activity<=1'b0;
        else activity<=^{i_sample,q_sample,valid,first,last};
endmodule
