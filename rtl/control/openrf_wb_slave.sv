// Wishbone B4 Classic, byte addresses. Request capture A, execution/response B,
// master consumes response C. Next request may be captured D with CYC held high.
// req_o is a single execution-edge event. See docs/control_plane.md.
module openrf_wb_slave (
    input logic wb_clk_i, wb_rst_i, wb_cyc_i, wb_stb_i, wb_we_i,
    input logic [15:0] wb_adr_i,
    input logic [31:0] wb_dat_i,
    input logic [3:0] wb_sel_i,
    output logic [31:0] wb_dat_o,
    output logic wb_ack_o, wb_err_o,
    output logic req_o, we_o,
    output logic [15:0] addr_o,
    output logic [31:0] wdata_o,
    output logic [3:0] sel_o,
    input logic [31:0] rdata_i,
    input logic error_i
);
    typedef enum logic [1:0] {IDLE, EXECUTE, RESPONSE} state_t;
    state_t state;
    logic ack, err;
    assign req_o = state == EXECUTE && wb_cyc_i && wb_stb_i && !wb_rst_i;
    assign wb_ack_o = ack && wb_cyc_i && wb_stb_i && !wb_rst_i;
    assign wb_err_o = err && wb_cyc_i && wb_stb_i && !wb_rst_i;
    always_ff @(posedge wb_clk_i) begin
        if (wb_rst_i) begin
            state <= IDLE; ack <= 1'b0; err <= 1'b0; wb_dat_o <= 32'd0;
            we_o <= 1'b0; addr_o <= 16'd0; wdata_o <= 32'd0; sel_o <= 4'd0;
        end else begin
            ack <= 1'b0; err <= 1'b0;
            case (state)
                IDLE: if (wb_cyc_i && wb_stb_i) begin
                    we_o <= wb_we_i; addr_o <= wb_adr_i;
                    wdata_o <= wb_dat_i; sel_o <= wb_sel_i; state <= EXECUTE;
                end
                EXECUTE: begin
                    if (req_o) begin
                        wb_dat_o <= error_i ? 32'd0 : rdata_i;
                        ack <= !error_i; err <= error_i;
                        state <= RESPONSE;
                    end else state <= IDLE;
                end
                RESPONSE: state <= IDLE;
                default: state <= IDLE;
            endcase
        end
    end
endmodule
