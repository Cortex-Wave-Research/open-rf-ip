// Fixed, fully decoded Harvard instruction / data interfaces; shared dual-read ROM.
// RAM is initialized by firmware, not by a reset loop that prevents RAM inference.
module openrf_cpu_memory #(
    parameter ROM_FILE = "build/vexriscv/firmware/firmware.hex"
) (
    input logic clk, rst,
    input logic i_valid,
    input logic [31:0] i_pc,
    output logic i_ready, i_rsp_valid, i_error,
    output logic [31:0] i_inst,
    input logic d_valid, d_wr,
    input logic [31:0] d_address, d_data,
    input logic [3:0] d_mask,
    input logic [1:0] d_size,
    output logic d_ready, d_rsp_ready, d_error,
    output logic [31:0] d_rdata,
    output logic wb_cyc, wb_stb, wb_we,
    output logic [15:0] wb_addr,
    output logic [31:0] wb_wdata,
    output logic [3:0] wb_sel,
    input logic wb_ack, wb_err,
    input logic [31:0] wb_rdata,
    output logic [31:0] mailbox_o,
    output logic bus_fault
);
    logic [31:0] rom [0:1023];
    logic [31:0] ram [0:255];
    initial $readmemh(ROM_FILE, rom);
    logic local_pending, local_rsp, local_error;
    logic [31:0] local_data;
    logic adapter_ready, adapter_rsp, adapter_error, adapter_fault;
    logic [31:0] adapter_data;
    wire mmio = d_address[31:16] == 16'h4000;
    wire rom_hit = d_address[31:12] == 20'h80000;
    wire ram_hit = d_address[31:10] == 22'h200040;
    wire aligned = (d_size == 0) || (d_size == 1 && !d_address[0]) ||
                   (d_size == 2 && d_address[1:0] == 0);
    wire instruction_hit = i_pc[31:12] == 20'h80000 && i_pc[1:0] == 0;
    assign i_ready = !rst;
    assign d_ready = adapter_ready && !local_pending && !rst;
    assign d_rsp_ready = local_rsp || adapter_rsp;
    assign d_error = local_error || adapter_error;
    assign d_rdata = adapter_rsp ? adapter_data : local_data;
    openrf_dbus_wishbone adapter (
        .clk(clk),.rst(rst),.cmd_valid(d_valid && mmio && !local_pending),
        .cmd_wr(d_wr),.cmd_address(d_address),.cmd_data(d_data),.cmd_mask(d_mask),
        .cmd_ready(adapter_ready),.rsp_ready(adapter_rsp),.rsp_error(adapter_error),
        .rsp_data(adapter_data),.fault(adapter_fault),.*);
    // No reset on the ROM output registers: response-valid controls consumption.
    always_ff @(posedge clk) begin
        if (i_valid && i_ready) i_inst <= instruction_hit ? rom[i_pc[11:2]] : 32'h0000006f;
        if (d_valid && d_ready && !mmio && aligned) begin
            if (rom_hit) local_data <= rom[d_address[11:2]];
            else if (ram_hit) begin
                local_data <= ram[d_address[9:2]];
                if (d_wr) begin
                    for (integer lane=0; lane<4; lane=lane+1)
                        if (d_mask[lane]) ram[d_address[9:2]][8*lane +: 8] <= d_data[8*lane +: 8];
                end
            end else if (d_address == 32'h40010000) local_data <= mailbox_o;
            else if (d_address == 32'h40010004) local_data <= {31'd0,bus_fault};
            else local_data <= 32'd0;
        end
    end
    always_ff @(posedge clk) begin
        if (rst) begin
            i_rsp_valid <= 1'b0; i_error <= 1'b0;
            local_pending <= 1'b0; local_rsp <= 1'b0; local_error <= 1'b0;
            mailbox_o <= 32'd0; bus_fault <= 1'b0;
        end else begin
            i_rsp_valid <= i_valid && i_ready;
            i_error <= i_valid && i_ready && !instruction_hit;
            local_pending <= 1'b0; local_rsp <= 1'b0; local_error <= 1'b0;
            if (adapter_fault) bus_fault <= 1'b1;
            if (d_valid && d_ready && !mmio) begin
                local_pending <= 1'b1;
                local_rsp <= !d_wr;
                if (!aligned || (!rom_hit && !ram_hit && d_address != 32'h40010000 && d_address != 32'h40010004) ||
                    (d_wr && rom_hit) || (d_wr && d_address == 32'h40010004) ||
                    ((d_address == 32'h40010000 || d_address == 32'h40010004) && (d_size != 2 || d_mask != 15))) begin
                    bus_fault <= 1'b1; local_error <= 1'b1;
                end else if (d_wr && d_address == 32'h40010000) mailbox_o <= d_data;
            end
        end
    end
endmodule
