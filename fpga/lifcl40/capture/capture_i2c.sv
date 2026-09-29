// Board-only, 12 MHz oversampled I2C target. 25 kHz host, no clock stretching.
// Address 0x2a, two-byte big-endian byte pointer, repeated START then read.
module capture_i2c (
    input logic clk, rst, scl, sda_in,
    output logic sda_low,
    output logic [12:0] byte_address,
    input logic [7:0] read_data
);
    logic [2:0] scl_sync, sda_sync;
    wire rise = scl_sync[2:1] == 2'b01;
    wire fall = scl_sync[2:1] == 2'b10;
    wire start_seen = scl_sync[2] && scl_sync[1] && sda_sync[2:1] == 2'b10;
    wire stop_seen = scl_sync[2] && scl_sync[1] && sda_sync[2:1] == 2'b01;
    typedef enum logic [3:0] {IDLE, ADDRESS, ACK_PREP, ACK_HOLD,
        PTR_HI, PTR_LO, TX_PREP, TX, ACK_RELEASE, MASTER_ACK, NEXT_BYTE} state_t;
    state_t state, after_ack;
    logic [6:0] rx;
    logic [2:0] bit_count;
    logic master_more;
    always_ff @(posedge clk) begin
        scl_sync <= {scl_sync[1:0],scl};
        sda_sync <= {sda_sync[1:0],sda_in};
        if (rst) begin
            scl_sync <= 3'b111; sda_sync <= 3'b111;
            state <= IDLE; after_ack <= IDLE; sda_low <= 1'b0;
            byte_address <= '0; rx <= '0; bit_count <= '0; master_more <= 1'b0;
        end else if (start_seen) begin
            state <= ADDRESS; bit_count <= 3'd7; sda_low <= 1'b0;
        end else if (stop_seen) begin
            state <= IDLE; sda_low <= 1'b0;
        end else begin
            case (state)
                ADDRESS, PTR_HI, PTR_LO: if (rise) begin
                    rx <= {rx[5:0],sda_sync[2]};
                    if (bit_count != 0) bit_count <= bit_count - 1'b1;
                    else if (state == ADDRESS) begin
                        if (rx[6:0] == 7'h2a) begin
                            after_ack <= sda_sync[2] ? TX_PREP : PTR_HI;
                            state <= ACK_PREP;
                        end else state <= IDLE;
                    end else begin
                        if (state == PTR_HI) begin
                            byte_address[12:8] <= {rx[3:0],sda_sync[2]};
                            after_ack <= PTR_LO;
                        end else begin
                            byte_address[7:0] <= {rx[6:0],sda_sync[2]};
                            after_ack <= IDLE;
                        end
                        state <= ACK_PREP;
                    end
                end
                ACK_PREP: if (fall) begin sda_low <= 1'b1; state <= ACK_HOLD; end
                ACK_HOLD: if (fall) begin
                    sda_low <= 1'b0; state <= after_ack; bit_count <= 3'd7;
                    if (after_ack == TX_PREP) begin
                        sda_low <= ~read_data[7]; state <= TX;
                    end
                end
                TX: if (fall) begin
                    if (bit_count == 0) begin sda_low <= 1'b0; state <= MASTER_ACK; end
                    else begin
                        bit_count <= bit_count - 1'b1;
                        sda_low <= ~read_data[bit_count-3'd1];
                    end
                end
                MASTER_ACK: if (rise) begin master_more <= ~sda_sync[2]; state <= NEXT_BYTE; end
                NEXT_BYTE: if (fall) begin
                    if (master_more) begin byte_address <= byte_address + 1'b1; state <= TX_PREP; end
                    else begin state <= IDLE; sda_low <= 1'b0; end
                end
                // Address changed on preceding clock; allow synchronous RAM read.
                TX_PREP: begin state <= ACK_RELEASE; end
                ACK_RELEASE: begin sda_low <= ~read_data[7]; bit_count <= 3'd7; state <= TX; end
                default: begin state <= IDLE; sda_low <= 1'b0; end
            endcase
        end
    end
endmodule
