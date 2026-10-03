// RFC2: 39 meaningful bits per sample, sent in five little-endian bytes.
// I[17:0], Q[35:18], valid[36], start[37], end[38], reserved[39]=0.
// 1024x39 RAM, frozen after first block; original RFC1 store stays unchanged.
module hp_capture_store (
    input logic clk, rst,
    input logic signed [17:0] i_sample, q_sample,
    input logic valid, chirp_start, chirp_end,
    input logic [12:0] byte_address,
    output logic [7:0] read_data,
    output logic done, error
);
    logic [38:0] ram [0:1023];
    logic [9:0] wr;
    logic active;
    logic [38:0] rd;
    wire [12:0] payload_address = byte_address - 13'd16;
    // Exact division by 5 for every 13-bit address: floor(n*3277 / 16384).
    // 5*3277=16385; n=5q+r implies q+floor((q+3277r)/16384)=q,
    // since 0<=q<=1638 and 0<=r<=4, hence q+3277r<=14746<16384.
    // Explicit shift/add avoids a generic divider or inferred DSP multiplier.
    wire [24:0] extended_address = {12'd0,payload_address};
    wire [24:0] unused_scaled_address = (extended_address << 11) +
        (extended_address << 10) + (extended_address << 7) +
        (extended_address << 6) + (extended_address << 3) +
        (extended_address << 2) + extended_address;
    wire [12:0] unused_word_address = {2'd0,unused_scaled_address[24:14]};
    wire [12:0] byte_select = payload_address -
        ((unused_word_address << 2) + unused_word_address);
    always_ff @(posedge clk) begin
        rd <= ram[unused_word_address[9:0]];
        if (rst) begin
            wr <= 10'd0; active <= 1'b0; done <= 1'b0; error <= 1'b0;
        end else if (!done && !error) begin
            if (active && !valid) begin error <= 1'b1; active <= 1'b0; end
            else if (valid && (active || chirp_start)) begin
                ram[wr] <= {chirp_end,chirp_start,valid,q_sample,i_sample};
                if (wr == 10'd1023) begin done <= 1'b1; active <= 1'b0; end
                else begin wr <= wr + 10'd1; active <= 1'b1; end
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
                3: read_data = "2";
                4: read_data = 8'd2;
                5: read_data = {6'd0,error,done};
                6: read_data = 8'd0;
                7: read_data = 8'd4;
                8: read_data = 8'd5;
                9: read_data = 8'd18;
                default: read_data = 8'd0;
            endcase
        end else if (byte_address < 13'd5136 && done) begin
            case (byte_select)
                13'd0: read_data = rd[7:0];
                13'd1: read_data = rd[15:8];
                13'd2: read_data = rd[23:16];
                13'd3: read_data = rd[31:24];
                13'd4: read_data = {1'b0,rd[38:32]};
                default: read_data = 8'd0;
            endcase
        end
    end
endmodule
