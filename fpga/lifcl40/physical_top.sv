// Physical liveness harness only. Native 12 MHz, no PLL, compact verified core.
module physical_top #(
    parameter integer HEARTBEAT_HALF_CYCLES = 6000000,
    parameter integer CHIRPS_PER_TOGGLE = 300
)(
    input logic clk,
    output logic heartbeat_n,
    output logic chirp_led_n
);
    localparam integer HB_BITS = $clog2(HEARTBEAT_HALF_CYCLES);
    localparam integer DONE_BITS = $clog2(CHIRPS_PER_TOGGLE);
    logic [3:0] startup = 4'b1111;
    logic [HB_BITS-1:0] heartbeat_count;
    logic [DONE_BITS-1:0] completion_count;
    logic heartbeat, completed;
    // Keep the actual I/Q datapath in the configuration without routing samples
    // to pins. Its internal signature is retained solely for implementation audit.
    logic signed [13:0] i_sample, q_sample;
    (* keep = 1 *) logic unused_datapath_signature;
    logic sample_valid, chirp_end, busy;
    logic unused_chirp_start;
    logic [31:0] unused_phase_increment, unused_chirp_count;
    always_ff @(posedge clk) startup <= {startup[2:0],1'b0};
    rf_chirp_nco chirp (
        .clk(clk),.rst(startup[3]),.enable(1'b1),.start(1'b1),
        .start_phase_inc(32'd178956971),.chirp_step(32'sd53692),
        .chirp_length(32'd10000),.repeat_mode(1'b1),
        .i_out(i_sample),.q_out(q_sample),.sample_valid(sample_valid),
        .chirp_start(unused_chirp_start),.chirp_end(chirp_end),.busy(busy),
        .phase_increment(unused_phase_increment),.chirp_count(unused_chirp_count)
    );
    assign heartbeat_n = ~heartbeat;
    assign chirp_led_n = ~completed;
    always_ff @(posedge clk) begin
        if (startup[3]) begin
            heartbeat_count <= '0;
            completion_count <= '0;
            heartbeat <= 1'b0;
            completed <= 1'b0;
            unused_datapath_signature <= 1'b0;
        end else begin
            unused_datapath_signature <= ^{i_sample,q_sample,sample_valid};
            if (heartbeat_count == HB_BITS'(HEARTBEAT_HALF_CYCLES-1)) begin
                heartbeat_count <= '0;
                heartbeat <= ~heartbeat;
            end else heartbeat_count <= heartbeat_count + 1'b1;
            // Registered end/valid flags refer to the preceding emission edge.
            if (chirp_end && sample_valid && busy) begin
                if (completion_count == DONE_BITS'(CHIRPS_PER_TOGGLE-1)) begin
                    completion_count <= '0;
                    completed <= ~completed;
                end else completion_count <= completion_count + 1'b1;
            end
        end
    end
endmodule
