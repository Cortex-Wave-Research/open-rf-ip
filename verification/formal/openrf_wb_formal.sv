// Inputs remain arbitrary, including legal holds and aborted transactions.
module openrf_wb_formal(
    input wb_clk_i, wb_rst_i, wb_cyc_i, wb_stb_i, wb_we_i,
    input [15:0] wb_adr_i, input [31:0] wb_dat_i, input [3:0] wb_sel_i,
    input [31:0] rdata_i, input error_i,
    output [2:0] reached
);
    wire [31:0] wb_dat_o, wdata_o;
    wire wb_ack_o, wb_err_o, req_o, we_o;
    wire [15:0] addr_o;
    wire [3:0] sel_o;
    openrf_wb_slave dut(.*);
    reg past_valid=0;
    reg [1:0] phase=0;
    reg [2:0] cover_seen=0;
    assign reached=cover_seen;
    wire request=wb_cyc_i && wb_stb_i;
    always @(posedge wb_clk_i) begin
        past_valid<=1;
        if (!past_valid) assume(wb_rst_i);
        if (wb_rst_i) begin phase<=0; cover_seen<=0; end
        else case(phase)
            0: if(request) phase<=1;
            1: phase<=request ? 2 : 0;
            2: phase<=0;
            default: phase<=0; // total ghost transition relation for induction
        endcase
        if (past_valid) begin
            // p_exclusive
            assert(!(wb_ack_o && wb_err_o));
            // p_no_unrequested_response
            if(!request || wb_rst_i) assert(!wb_ack_o && !wb_err_o);
            // p_execution
            assert(req_o==(phase==1 && request && !wb_rst_i));
            if ($past(wb_rst_i)) begin
                // p_reset
                assert(!wb_ack_o && !wb_err_o && !req_o && wb_dat_o==0);
            end else begin
                // p_ack_latency
                assert(wb_ack_o==($past(req_o && !error_i) && request && !wb_rst_i));
                // p_err_latency
                assert(wb_err_o==($past(req_o && error_i) && request && !wb_rst_i));
                // p_no_duplicate
                if($past(wb_ack_o || wb_err_o)) assert(!wb_ack_o && !wb_err_o);
                // p_capture
                if($past(phase==0 && request))
                    assert({we_o,addr_o,wdata_o,sel_o}==$past({wb_we_i,wb_adr_i,wb_dat_i,wb_sel_i}));
                // p_response_data
                if($past(req_o)) assert(wb_dat_o==($past(error_i) ? 32'd0 : $past(rdata_i)));
            end
        end
        if (!wb_rst_i) begin
            if(wb_ack_o) cover_seen[0]<=1;
            if(wb_err_o) cover_seen[1]<=1;
            if(phase==1 && !request) cover_seen[2]<=1;
        end
    end
endmodule
