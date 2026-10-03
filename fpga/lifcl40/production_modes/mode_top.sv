// Equivalent NCO-only resource/timing harness: Fs/12, startup reset, XOR signature.
// Constant controls specialize both modes. No external sample-interface timing claim.
module mode_top #(parameter integer HIGH_PURITY=0) (
    input logic clk,
    output logic activity
);
    localparam integer P=(HIGH_PURITY != 0) ? 64 : 32;
    localparam integer B=(HIGH_PURITY != 0) ? 18 : 14;
    localparam logic [P-1:0] WORD=(HIGH_PURITY != 0) ? P'(64'h1555555555555555) : P'(32'h15555555);
    logic [3:0] startup=4'b1111;
    logic signed [B-1:0] i_sample,q_sample;
    logic valid;
    always_ff @(posedge clk) startup <= {startup[2:0],1'b0};
    rf_nco_mode #(.HIGH_PURITY(HIGH_PURITY)) nco (
        .clk(clk),.rst(startup[3]),.enable(1'b1),.phase_increment(WORD),
        .i_out(i_sample),.q_out(q_sample),.sample_valid(valid));
    always_ff @(posedge clk)
        if (startup[3]) activity<=1'b0;
        else activity<=^{i_sample,q_sample,valid};
endmodule
