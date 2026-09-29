// Portable composition; rf_nco is unchanged. See docs/chirp_architecture.md.
module rf_chirp_nco (
    input  logic clk,
    input  logic rst,
    input  logic enable,
    input  logic start,
    input  logic [31:0] start_phase_inc,
    input  logic signed [31:0] chirp_step,
    input  logic [31:0] chirp_length,
    input  logic repeat_mode,
    output logic signed [13:0] i_out,
    output logic signed [13:0] q_out,
    output logic sample_valid,
    output logic chirp_start,
    output logic chirp_end,
    output logic busy,
    output logic [31:0] phase_increment,
    output logic [31:0] chirp_count
);
    logic nco_enable;
    chirp_controller controller (
        .clk(clk), .rst(rst), .enable(enable), .start(start),
        .start_phase_inc(start_phase_inc), .chirp_step(chirp_step),
        .chirp_length(chirp_length), .repeat_mode(repeat_mode),
        .phase_increment(phase_increment), .chirp_count(chirp_count),
        .nco_enable(nco_enable), .busy(busy),
        .chirp_start(chirp_start), .chirp_end(chirp_end)
    );
    rf_nco #(.PHASE_WIDTH(32), .OUTPUT_WIDTH(14), .LUT_ADDR_WIDTH(10)) nco (
        .clk(clk), .rst(rst), .enable(nco_enable),
        .phase_increment(phase_increment), .i_out(i_out), .q_out(q_out),
        .sample_valid(sample_valid)
    );
endmodule
