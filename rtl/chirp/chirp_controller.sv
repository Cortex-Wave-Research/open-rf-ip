// Fixed-width linear chirp scheduler; see docs/chirp_architecture.md.
module chirp_controller (
    input  logic clk,
    input  logic rst,
    input  logic enable,
    input  logic start,
    input  logic [31:0] start_phase_inc,
    input  logic signed [31:0] chirp_step,
    input  logic [31:0] chirp_length,
    input  logic repeat_mode,
    output logic [31:0] phase_increment,
    output logic [31:0] chirp_count,
    output logic nco_enable,
    output logic busy,
    output logic chirp_start,
    output logic chirp_end
);
    logic [31:0] start_word;
    logic signed [31:0] step_word;
    logic [31:0] last_count;
    logic repeat_latched;

    assign nco_enable = busy && enable && !rst;

    always_ff @(posedge clk) begin
        if (rst) begin
            start_word <= 32'd0;
            step_word <= 32'sd0;
            last_count <= 32'd0;
            repeat_latched <= 1'b0;
            phase_increment <= 32'd0;
            chirp_count <= 32'd0;
            busy <= 1'b0;
            chirp_start <= 1'b0;
            chirp_end <= 1'b0;
        end else begin
            chirp_start <= 1'b0;
            chirp_end <= 1'b0;
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
                chirp_start <= (chirp_count == 32'd0);
                chirp_end <= (chirp_count == last_count);
                if (chirp_count == last_count) begin
                    if (repeat_latched) begin
                        phase_increment <= start_word;
                        chirp_count <= 32'd0;
                    end else begin
                        busy <= 1'b0;
                    end
                end else begin
                    // Reinterpret signed step as its unsigned two's-complement
                    // bits, add, and explicitly retain the low 32 bits (mod 2^32).
                    phase_increment <= 32'(phase_increment + $unsigned(step_word));
                    chirp_count <= chirp_count + 32'd1;
                end
            end
        end
    end
endmodule
