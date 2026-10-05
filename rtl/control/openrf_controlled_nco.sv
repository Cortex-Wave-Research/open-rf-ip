// Thin control wrapper: all numerical samples come from frozen production RTL.
module openrf_controlled_nco #(
    parameter integer HIGH_PURITY=0,
    parameter integer OUTPUT_WIDTH=(HIGH_PURITY != 0) ? 18 : 14
) (
    input logic wb_clk_i, wb_rst_i, wb_cyc_i, wb_stb_i, wb_we_i,
    input logic [15:0] wb_adr_i,
    input logic [31:0] wb_dat_i,
    input logic [3:0] wb_sel_i,
    output logic [31:0] wb_dat_o,
    output logic wb_ack_o, wb_err_o,
    output logic signed [OUTPUT_WIDTH-1:0] i_out, q_out,
    output logic sample_valid, chirp_start, chirp_end
);
    localparam integer P=(HIGH_PURITY != 0) ? 64 : 32;
    logic run_enable, config_valid, start_pulse;
    logic [63:0] active_nco, unused_start;
    logic signed [63:0] unused_step;
    logic [31:0] unused_length;
    logic unused_repeat, unused_start_pulse;
    logic engine_busy, engine_done;
    openrf_control #(.HIGH_PURITY(HIGH_PURITY),.ENGINE_KIND(0)) control (
        .engine_busy_i(engine_busy),.engine_done_i(engine_done),
        .start_o(start_pulse),.run_enable_o(run_enable),.config_valid_o(config_valid),
        .active_nco_o(active_nco),
        .active_start_o(unused_start),
        .active_step_o(unused_step),
        .active_length_o(unused_length),
        .active_repeat_o(unused_repeat),.*);
    assign unused_start_pulse = start_pulse;
    assign engine_busy = run_enable && config_valid;
    assign engine_done = 1'b0;
    assign chirp_start = 1'b0;
    assign chirp_end = 1'b0;
    rf_nco_mode #(.HIGH_PURITY(HIGH_PURITY),.OUTPUT_WIDTH(OUTPUT_WIDTH)) engine (
        .clk(wb_clk_i),.rst(wb_rst_i),.enable(run_enable && config_valid),
        .phase_increment(P'(active_nco)),.*);
    // CSR validation guarantees these compact upper bits are zero/sign-extension.
    if (HIGH_PURITY == 0) begin : compact_width_check_boundary
        wire [31:0] unused_active_nco_high = active_nco[63:32];
    end
endmodule
