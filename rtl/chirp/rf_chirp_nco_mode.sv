// Elaboration-time modes. Compact composition remains source-identical.
// busy/count/increment are scheduler state, not delayed sample metadata.
// HP busy may drop one enabled edge before the last valid/end sample drains.
module rf_chirp_nco_mode #(
    parameter integer HIGH_PURITY = 0,
    parameter integer PHASE_WIDTH = (HIGH_PURITY != 0) ? 64 : 32,
    parameter integer OUTPUT_WIDTH = (HIGH_PURITY != 0) ? 18 : 14
) (
    input logic clk, rst, enable, start,
    input logic [PHASE_WIDTH-1:0] start_phase_inc,
    input logic signed [PHASE_WIDTH-1:0] chirp_step,
    input logic [31:0] chirp_length,
    input logic repeat_mode,
    output logic signed [OUTPUT_WIDTH-1:0] i_out, q_out,
    output logic sample_valid, chirp_start, chirp_end, busy,
    output logic [PHASE_WIDTH-1:0] phase_increment,
    output logic [31:0] chirp_count
);
    if ((HIGH_PURITY != 0 && HIGH_PURITY != 1) ||
        PHASE_WIDTH != ((HIGH_PURITY != 0) ? 64 : 32) ||
        OUTPUT_WIDTH != ((HIGH_PURITY != 0) ? 18 : 14)) begin : invalid_configuration
        initial $fatal(1, "chirp modes support only COMPACT 32/14 or HIGH_PURITY 64/18");
    end
    if (HIGH_PURITY != 0) begin : high_purity
        logic nco_enable;
        chirp_controller #(.PHASE_WIDTH(64), .MARKER_DELAY(1)) controller (
            .clk(clk), .rst(rst), .enable(enable), .start(start),
            .start_phase_inc(start_phase_inc), .chirp_step(chirp_step),
            .chirp_length(chirp_length), .repeat_mode(repeat_mode),
            .phase_increment(phase_increment), .chirp_count(chirp_count),
            .nco_enable(nco_enable), .busy(busy),
            .chirp_start(chirp_start), .chirp_end(chirp_end));
        rf_nco_high_purity nco (.clk(clk), .rst(rst), .enable(enable),
            .sample_enable(nco_enable), .phase_increment(phase_increment),
            .i_out(i_out), .q_out(q_out), .sample_valid(sample_valid));
    end else begin : compact
        rf_chirp_nco chirp (.*);
    end
endmodule
