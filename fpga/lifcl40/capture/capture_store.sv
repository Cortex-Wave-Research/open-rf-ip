// Passive tap: first 1024 consecutive valid samples starting at chirp_start.
// RAM is never reset or written again after done. A gap aborts with error.
module capture_store (
    input logic clk, rst,
    input logic signed [13:0] i_sample, q_sample,
    input logic valid, chirp_start, chirp_end,
    input logic [12:0] byte_address,
    output logic [7:0] read_data,
    output logic done, error
);
    logic [31:0] ram [0:1023];
    logic [9:0] wr;
    logic active;
    logic [31:0] rd;
    wire [12:0] unused_payload_address = byte_address - 13'd16;
    always_ff @(posedge clk) begin
        rd <= ram[unused_payload_address[11:2]];
        if (rst) begin wr <= '0; active <= 1'b0; done <= 1'b0; error <= 1'b0; end
        else if (!done && !error) begin
            if (active && !valid) begin error <= 1'b1; active <= 1'b0; end
            else if (valid && (active || chirp_start)) begin
                ram[wr] <= {1'b0,chirp_end,chirp_start,valid,q_sample,i_sample};
                if (wr == 10'd1023) begin done <= 1'b1; active <= 1'b0; end
                else begin wr <= wr + 1'b1; active <= 1'b1; end
            end
        end
    end
    always_comb begin
        read_data = 8'd0;
        if (byte_address < 13'd16) begin
            case (byte_address[3:0])
                0: read_data = "R";
                1: read_data = "F";
                2: read_data = "C";
                3: read_data = "1";
                4: read_data = 8'd1; // version
                5: read_data = {6'd0,error,done};
                6: read_data = 8'd0; // 1024, little endian
                7: read_data = 8'd4;
                8: read_data = 8'd4; // bytes/record
                9: read_data = 8'd14;
                default: read_data = 8'd0;
            endcase
        end else if (byte_address < 13'd4112 && done)
            read_data = rd[8*byte_address[1:0] +: 8];
    end
endmodule
