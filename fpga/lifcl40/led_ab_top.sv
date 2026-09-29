// Clock-free board proof. SWAP=0: D3 on/D4 off; SWAP=1: D3 off/D4 on.
module led_ab_top #(
    parameter bit SWAP = 1'b0
)(
    output logic led0,
    output logic led1
);
    assign led0 = SWAP;
    assign led1 = ~SWAP;
endmodule
