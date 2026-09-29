// Clockless board I/O test. Active-low LEDs: D3 on, D4 off.
module static_led_top (
    output logic led0,
    output logic led1
);
    assign led0 = 1'b0;
    assign led1 = 1'b1;
endmodule
