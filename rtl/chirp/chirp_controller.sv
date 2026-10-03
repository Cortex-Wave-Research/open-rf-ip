// Width-parameterized scheduler. Defaults preserve the compact numerical contract.
// MARKER_DELAY=1 aligns with the two-stage high-purity NCO; enable stalls both.
module chirp_controller #(
    parameter integer PHASE_WIDTH = 32,
    parameter integer MARKER_DELAY = 0
) (
    input  logic clk,
    input  logic rst,
    input  logic enable,
    input  logic start,
    input  logic [PHASE_WIDTH-1:0] start_phase_inc,
    input  logic signed [PHASE_WIDTH-1:0] chirp_step,
    input  logic [31:0] chirp_length,
    input  logic repeat_mode,
    output logic [PHASE_WIDTH-1:0] phase_increment,
    output logic [31:0] chirp_count,
    output logic nco_enable,
    output logic busy,
    output logic chirp_start,
    output logic chirp_end
);
    logic [PHASE_WIDTH-1:0] start_word;
    logic signed [PHASE_WIDTH-1:0] step_word;
    logic [31:0] last_count;
    logic repeat_latched;
    logic start_pending, end_pending;
    if ((PHASE_WIDTH != 32 && PHASE_WIDTH != 64) ||
        (MARKER_DELAY != 0 && MARKER_DELAY != 1)) begin : invalid_configuration
        initial $fatal(1, "controller supports PHASE_WIDTH 32/64 and MARKER_DELAY 0/1");
    end
    if (MARKER_DELAY == 0) begin : direct_markers
        assign chirp_start = start_pending;
        assign chirp_end = end_pending;
    end else begin : delayed_markers
        always_ff @(posedge clk) begin
            if (rst) begin
                chirp_start <= 1'b0;
                chirp_end <= 1'b0;
            end else begin
                chirp_start <= enable && start_pending;
                chirp_end <= enable && end_pending;
            end
        end
    end

    assign nco_enable = busy && enable && !rst;

    always_ff @(posedge clk) begin
        if (rst) begin
            start_word <= '0;
            step_word <= '0;
            last_count <= 32'd0;
            repeat_latched <= 1'b0;
            phase_increment <= '0;
            chirp_count <= 32'd0;
            busy <= 1'b0;
            start_pending <= 1'b0;
            end_pending <= 1'b0;
        end else begin
            if (enable || MARKER_DELAY == 0) begin
                start_pending <= 1'b0;
                end_pending <= 1'b0;
            end
            if (!busy) begin
                if (enable && start && chirp_length != 32'd0) begin
                    start_word <= start_phase_inc;
                    step_word <= chirp_step;
                    // Length is nonzero here, so this subtraction cannot underflow.
                    last_count <= chirp_length - 32'd1;
                    repeat_latched <= repeat_mode;
                    phase_increment <= start_phase_inc;
                    chirp_count <= 32'd0;
                    busy <= 1'b1;
                end
            end else if (enable) begin
                start_pending <= (chirp_count == 32'd0);
                end_pending <= (chirp_count == last_count);
                if (chirp_count == last_count) begin
                    if (repeat_latched) begin
                        phase_increment <= start_word;
                        chirp_count <= 32'd0;
                    end else begin
                        busy <= 1'b0;
                    end
                end else begin
                    // Reinterpret signed step as its unsigned two's-complement
                    // bits, add, and explicitly retain the low PHASE_WIDTH bits (mod 2^PHASE_WIDTH).
                    phase_increment <= PHASE_WIDTH'(phase_increment + $unsigned(step_word));
                    chirp_count <= chirp_count + 32'd1;
                end
            end
        end
    end
endmodule
