#!/usr/bin/env python
"""CRC Generator

Generates combinatorial LFSR/CRC logic in Verilog.

Usage: crcgen [OPTION]...
  -?, --help        display this help and exit
  -w, --width       specify width of CRC (default 32)
  -d, --datawidth   specify width of input data bus (default 8)
  -p, --poly        specify CRC polynomial (default 0x04c11db7)
  -i, --init        specify CRC initial state (default -1)
  -b, --bare        only generate combinatorial logic
  -n, --name        specify module name
  -o, --output      specify output file name
"""

import sys
import getopt
import collections
import copy
from jinja2 import Template

class Usage(Exception):
    def __init__(self, msg):
        self.msg = msg

def main(argv=None):
    if argv is None:
        argv = sys.argv
    try:
        try:
            opts, args = getopt.getopt(argv[1:], "?w:d:p:i:bn:o:", ["help", "width=", "datawidth=", "poly=", "init=", "bare", "name=", "output="])
        except getopt.error as msg:
             raise Usage(msg)
        # more code, unchanged
    except Usage as err:
        print(err.msg, file=sys.stderr)
        print("for help use --help", file=sys.stderr)
        return 2
    
    width = 32
    datawidth = 8
    poly = 0x04c11db7
    init = -1
    bare = False
    name = None
    out_name = None
    
    # process options
    for o, a in opts:
        if o in ('-?', '--help'):
            print(__doc__)
            sys.exit(0)
        if o in ('-w', '--width'):
            width = int(a)
        if o in ('-d', '--datawidth'):
            datawidth = int(a)
        if o in ('-p', '--poly'):
            poly = int(a, 0)
        if o in ('-i', '--init'):
            init = int(a, 0)
        if o in ('-b', '--bare'):
            bare = True
        if o in ('-n', '--name'):
            name = a
        if o in ('-o', '--output'):
            out_name = a
    
    # process arguments
    #for arg in args:
    #    print(arg)
    
    if poly & 1 == 0:
        print("Error: polynomial must include zeroth order term", file=sys.stderr)
        return 2

    if name is None:
        name = "crc_%d_%d_0x%x%s" % (width, datawidth, poly, ('_bare' if bare else ''))

    if out_name is None:
        out_name = name + ".v"

    print("Opening file '%s'..." % out_name)
    
    try:
        out_file = open(out_name, 'w')
    except Exception as ex:
        print("Error opening \"%s\": %s" %(out_name, ex.strerror), file=sys.stderr)
        exit(1)

    print("Generating CRC module {0}...".format(name))

    # poly representation
    poly_str = '1'
    for i in range(width):
        if i > 0 and poly & (1 << i):
            poly_str = 'x' + (('^%d' % i) if i > 1 else '') + ' + ' + poly_str
    poly_str = 'x^%d + ' % width + poly_str

    # Simulate shift register
    #
    # (example for CRC16, 0x8005)
    #
    #  ,-------------------+---------------------------------+------------,
    #  |                   |                                 |            |
    #  |  .----.  .----.   V   .----.  .----.       .----.   V   .----.   | 
    #  `->|  0 |->|  1 |->(+)->|  2 |->|  3 |->...->| 14 |->(+)->| 15 |->(+)<-DIN (MSB first) 
    #     '----'  '----'       '----'  '----'       '----'       '----'
    #

    # list index is output pin
    # list elements are [last state, input data]
    # initial state is 1:1 mapping from previous state to next state
    crc_next = collections.deque([[[x], []] for x in range(width)])

    for i in range(datawidth-1, -1, -1):
        # determine shift in value
        # current value in last FF, XOR with input data bit (MSB first)
        val = copy.deepcopy(crc_next[-1])
        val[1].append(i)

        # shift
        crc_next.rotate(1)
        crc_next[0] = val

        # add XOR inputs at correct indicies
        for i in range(1, width):
            if poly & (1 << i):
                crc_next[i][0]+=val[0]
                crc_next[i][1]+=val[1]

    # optimize
    # since X^X = 0, bin and count identical inputs
    # keep one input if the total count is odd, discard the rest
    for i in range(width):
        for j in range(2):
            cnt = collections.Counter()
            for e in crc_next[i][j]:
                cnt[e] += 1
            lst = []
            for e in cnt:
                if cnt[e] % 2:
                    lst.append(e)
            lst.sort()
            crc_next[i][j] = lst

    # mask init value at the proper width
    init = ((1 << width) - 1) & init;

    t = Template(u"""/*

Copyright (c) 2014 Alex Forencich

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

*/

// Language: Verilog 2001

`timescale 1ns / 1ps

/*
 * CRC module {{name}}
 *
 * CRC width:      {{w}}
 * Data width:     {{dw}}
{%- if not bare %}
 * Initial value:  {{w}}'h{{'%x' % init}}
{%- endif %}
 * CRC polynomial: {{w}}'h{{'%x' % poly}}
 * 
 * {{poly_str}}
 *
 * Generated by crcgen.py
 * 
 */
module {{name}}
(
{%- if not bare %}
    input  wire clk,
    input  wire rst,

    input  wire [{{dw-1}}:0] data_in,
    input  wire data_in_valid,
    input  wire crc_init,
    output wire [{{w-1}}:0] crc_out
{%- else %}
    input  wire [{{dw-1}}:0] data_in,
    input  wire [{{w-1}}:0] crc_state,
    output wire [{{w-1}}:0] crc_next
{%- endif %}
);

{% if not bare -%}
reg [{{w-1}}:0] crc_state, crc_next;

assign crc_out = crc_next;

{% endif -%}
always @* begin
    {%- for p in range(w) %}
    crc_next[{{p}}] = {% if crc_next[p][0]|length == 0 and crc_next[p][1]|length == 0 -%}0{% else %}
        {%- for i in crc_next[p][0] %}{% if not loop.first %} ^ {% endif %}crc_state[{{i}}]{% endfor %}
        {%- for i in crc_next[p][1] %}{% if crc_next[p][0]|length != 0 or not loop.first %} ^ {% endif %}data_in[{{i}}] {%- endfor %}{% endif %};
    {%- endfor %}
end

{% if not bare -%}
always @(posedge clk or posedge rst) begin
    if (rst) begin
        crc_state <= {{w}}'h{{'%x' % init}};
    end else begin
        if (crc_init) begin
            crc_state <= {{w}}'h{{'%x' % init}};
        end else if (data_in_valid) begin
            crc_state <= crc_next;
        end
    end
end

{% endif -%}
endmodule

""")
    
    out_file.write(t.render(
        w=width,
        dw=datawidth,
        poly=poly,
        init=init,
        poly_str=poly_str,
        crc_next=crc_next,
        bare=bare,
        name=name
    ))

    print("Done")
    

if __name__ == "__main__":
    sys.exit(main())


