// Thin control wrapper: all numerical samples come from frozen production RTL.
module openrf_controlled_chirp #(
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
    logic [63:0] unused_nco, active_start;
    logic signed [63:0] active_step;
    logic [31:0] active_length;
    logic active_repeat, transaction_active, unused_scheduler_busy;
    logic engine_busy, engine_done;
    openrf_control #(.HIGH_PURITY(HIGH_PURITY),.ENGINE_KIND(1)) control (
        .engine_busy_i(engine_busy),.engine_done_i(engine_done),
        .start_o(start_pulse),.run_enable_o(run_enable),.config_valid_o(config_valid),
        .active_nco_o(unused_nco),
        .active_start_o(active_start),
        .active_step_o(active_step),
        .active_length_o(active_length),
        .active_repeat_o(active_repeat),.*);
    logic [P-1:0] unused_increment;
    logic signed [P-1:0] engine_step;
    logic [31:0] unused_count;
    // A sized net makes the validated narrowing explicit for both frontends.
    assign engine_step = $signed(active_step[P-1:0]);
    assign engine_done = sample_valid && chirp_end;
    // Include the final output stage, even when scheduler busy has already fallen.
    assign engine_busy = transaction_active;
    always_ff @(posedge wb_clk_i) begin
        if (wb_rst_i) transaction_active <= 1'b0;
        else begin
            if (engine_done && !active_repeat) transaction_active <= 1'b0;
            if (start_pulse) transaction_active <= 1'b1;
        end
    end
    rf_chirp_nco_mode #(.HIGH_PURITY(HIGH_PURITY),.OUTPUT_WIDTH(OUTPUT_WIDTH)) engine (
        .clk(wb_clk_i),.rst(wb_rst_i),.enable(run_enable && config_valid),
        .start(start_pulse),.start_phase_inc(P'(active_start)),
        .chirp_step(engine_step),.chirp_length(active_length),
        .repeat_mode(active_repeat),.busy(unused_scheduler_busy),
        .phase_increment(unused_increment),.chirp_count(unused_count),.*);
    // CSR validation guarantees these compact upper bits are zero/sign-extension.
    if (HIGH_PURITY == 0) begin : compact_width_check_boundary
        wire [31:0] unused_active_start_high = active_start[63:32];
        wire [31:0] unused_active_step_high = active_step[63:32];
    end
endmodule
