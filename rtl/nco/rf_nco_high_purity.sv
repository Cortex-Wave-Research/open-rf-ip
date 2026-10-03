// Portable Candidate C: 64-bit phase, 16-bit address, signed 18-bit I/Q.
// Two enabled edges: dual-read quarter ROM, then sign/endpoint reconstruction.
// enable pauses ALL state; sample_enable admits a phase sample on enabled edges.
// With enable=1/sample_enable=0 the pipeline drains once without advancing phase.
// See docs/high_purity_nco.md. Magnitudes 0..131071; -131072 is unused.
module rf_nco_high_purity (
    input logic clk, rst, enable, sample_enable,
    input logic [63:0] phase_increment,
    output logic signed [17:0] i_out, q_out,
    output logic sample_valid
);
    logic [63:0] phase;
    logic [15:0] q_address, i_address;
    logic [13:0] q_index, i_index;
    logic [16:0] rom [0:16383];
    logic [16:0] q_read, i_read;
    logic q_sign, i_sign, q_peak, i_peak, pending_valid;
    logic signed [17:0] q_magnitude, i_magnitude;
    initial begin
        `include "high_purity_quarter.svh"
    end
    assign q_address = phase[63:48];
    assign i_address = 16'(q_address + 16'd16384);
    // Modulo-16384 reflection; exact peaks bypass address zero.
    assign q_index = q_address[14] ? 14'(-q_address[13:0]) : q_address[13:0];
    assign i_index = i_address[14] ? 14'(-i_address[13:0]) : i_address[13:0];
    assign q_magnitude = $signed({1'b0, q_peak ? 17'd131071 : q_read});
    assign i_magnitude = $signed({1'b0, i_peak ? 17'd131071 : i_read});
    always_ff @(posedge clk) begin
        if (rst) begin
            phase <= 64'd0;
            q_read <= 17'd0; i_read <= 17'd0;
            q_sign <= 1'b0; i_sign <= 1'b0;
            q_peak <= 1'b0; i_peak <= 1'b0;
            pending_valid <= 1'b0; sample_valid <= 1'b0;
            i_out <= 18'sd0; q_out <= 18'sd0;
        end else begin
            sample_valid <= 1'b0;
            if (enable) begin
                pending_valid <= sample_enable;
                sample_valid <= pending_valid;
                if (pending_valid) begin
                    q_out <= q_sign ? -q_magnitude : q_magnitude;
                    i_out <= i_sign ? -i_magnitude : i_magnitude;
                end
                if (sample_enable) begin
                    phase <= 64'(phase + phase_increment);
                    q_read <= rom[q_index]; i_read <= rom[i_index];
                    q_sign <= q_address[15]; i_sign <= i_address[15];
                    q_peak <= q_address[14] && (q_address[13:0] == 14'd0);
                    i_peak <= i_address[14] && (i_address[13:0] == 14'd0);
                end
            end
        end
    end
endmodule
