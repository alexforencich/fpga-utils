#!/usr/bin/env python
"""
Generates combinatorial LFSR/CRC logic in Verilog.
"""

from __future__ import print_function

import argparse
import collections
import copy
from jinja2 import Template

def main():
    parser = argparse.ArgumentParser(description=__doc__.strip())
    parser.add_argument('-w', '--width',     type=int, default=32,           help="width of CRC (default 32)")
    parser.add_argument('-d', '--datawidth', type=int, default=8,            help="width of input data bus (default 8)")
    parser.add_argument('-p', '--poly',      type=str, default='0x04c11db7', help="CRC polynomial (default 0x04c11db7)")
    parser.add_argument('-i', '--init',      type=int, default=-1,           help="CRC initial state (default -1)")
    parser.add_argument('-c', '--config',    type=str, default='galois',
                                choices=['galois', 'fibonacci'],             help="LFSR configuration (default galois)")
    parser.add_argument('-l', '--load',      action='store_true',            help="include load logic")
    parser.add_argument('-b', '--bare',      action='store_true',            help="only generate combinatorial logic")
    parser.add_argument('-e', '--extend',    action='store_true',            help="extend state width to data width")
    parser.add_argument('-r', '--reverse',   action='store_true',            help="bit-reverse input and output")
    parser.add_argument('-n', '--name',      type=str,                       help="module name")
    parser.add_argument('-o', '--output',    type=str,                       help="output file name")

    args = parser.parse_args()

    try:
        generate(**args.__dict__)
    except IOError as ex:
        print(ex)
        exit(1)

def generate(width=32, datawidth=8, poly=0x04c11db7, init=-1, config='galois', load=False, bare=False, extend=False, reverse=False, name=None, output=None):
    poly = int(poly, 0)
    cmdline = "crcgen.py"
    cmdline += " -w {0}".format(width)
    cmdline += " -d {0}".format(datawidth)
    cmdline += " -p 0x{0:x}".format(poly)
    cmdline += " -i {0}".format(init)
    cmdline += " -c {0}".format(config)
    if load: cmdline += " -l"
    if bare: cmdline += " -b"
    if extend: cmdline += " -e"
    if reverse: cmdline += " -r"
    if name: cmdline += " -n {0}".format(name)
    if output: cmdline += " -o {0}".format(output)

    if config not in ('galois', 'fibonacci'):
        raise Exception("Invalid configuration '%s'" % config)

    if poly & 1 == 0:
        raise Exception("Polynomial must include zeroth order term")

    if name is None:
        name = "crc_%d_%d_0x%x" % (width, datawidth, poly)
        if load:
            name += '_load'
        if bare:
            name += '_bare'
        if reverse:
            name += '_rev'

    if output is None:
        output = name + ".v"

    print("Opening file '%s'..." % output)

    output_file = open(output, 'w')

    print("Generating CRC module {0}...".format(name))

    # poly representation
    poly_str = '1'
    for i in range(width):
        if i > 0 and poly & (1 << i):
            poly_str = 'x' + (('^%d' % i) if i > 1 else '') + ' + ' + poly_str
    poly_str = 'x^%d + ' % width + poly_str

    # Simulate shift register
    #
    # Galois style (example for CRC16, 0x8005)
    #
    #  ,-------------------+---------------------------------+------------,
    #  |                   |                                 |            |
    #  |  .----.  .----.   V   .----.  .----.       .----.   V   .----.   | 
    #  `->|  0 |->|  1 |->(+)->|  2 |->|  3 |->...->| 14 |->(+)->| 15 |->(+)<-DIN (MSB first) 
    #     '----'  '----'       '----'  '----'       '----'       '----'
    #
    # Fibonacci style (example for 64b66b, 0x8000000001)
    #
    #  ,-----------------------------(+)<------------------------------,
    #  |                              ^                                |
    #  |  .----.  .----.       .----. |  .----.       .----.  .----.   | 
    #  `->|  0 |->|  1 |->...->| 38 |-+->| 39 |->...->| 56 |->| 57 |->(+)<-DIN (MSB first) 
    #     '----'  '----'       '----'    '----'       '----'  '----'
    #

    # list index is output pin
    # list elements are [last state, input data]
    # initial state is 1:1 mapping from previous state to next state
    crc_next = collections.deque([[[x], []] for x in range(width)])
    extend_list = []

    if config == 'galois':
        # Galois configuration
        for i in range(datawidth-1, -1, -1):
            # determine shift in value
            # current value in last FF, XOR with input data bit (MSB first)
            val = copy.deepcopy(crc_next[-1])
            val[1].append(i)

            # shift
            crc_next.rotate(1)
            extend_list.insert(0, crc_next[0])
            crc_next[0] = val

            # add XOR inputs at correct indicies
            for i in range(1, width):
                if poly & (1 << i):
                    crc_next[i][0] += val[0]
                    crc_next[i][1] += val[1]
    elif config == 'fibonacci':
        # Fibonacci configuration
        for i in range(datawidth-1, -1, -1):
            # determine shift in value
            # current value in last FF, XOR with input data bit (MSB first)
            val = copy.deepcopy(crc_next[-1])
            val[1].append(i)

            # add XOR inputs from correct indicies
            for i in range(1, width):
                if poly & (1 << i):
                    val[0] += crc_next[i-1][0]
                    val[1] += crc_next[i-1][1]

            # shift
            crc_next.rotate(1)
            extend_list.insert(0, crc_next[0])
            crc_next[0] = val

    state_width = width

    if extend and datawidth > width:
        state_width = datawidth

        # add the bits that fell off the end while shifting
        crc_next += extend_list[:datawidth-width]

    # optimize
    # since X^X = 0, bin and count identical inputs
    # keep one input if the total count is odd, discard the rest
    for i in range(state_width):
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
    init = ((1 << state_width) - 1) & init;
    init2 = init;

    if reverse:
        # reverse outputs
        crc_next.reverse()
        for i in range(state_width):
            # reverse state input
            for j in range(len(crc_next[i][0])):
                crc_next[i][0][j] = state_width - crc_next[i][0][j] - 1
            crc_next[i][0].sort()
            # reverse data input
            for j in range(len(crc_next[i][1])):
                crc_next[i][1][j] = datawidth - crc_next[i][1][j] - 1
            crc_next[i][1].sort()
        # reverse init value
        init2 = int('{:0{width}b}'.format(init, width=state_width)[::-1], 2)

    t = Template(u"""/*

Copyright (c) 2014-2015 Alex Forencich

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
{%- if w != sw %}
 * State width:    {{sw}}
{%- endif %}
 * Data width:     {{dw}}
{%- if not bare %}
 * Initial value:  {{sw}}'h{{'%x' % init}}{%- if reverse %} (reversed: {{sw}}'h{{'%x' % init2}}){%- endif %}
{%- endif %}
 * CRC polynomial: {{w}}'h{{'%x' % poly}}
 * Configuration:  {{config}}
{%- if extend %}
 * Extend state:   yes
{%- endif %}
{%- if reverse %}
 * Bit-reverse:    input and output
{%- endif %}
 *
 * {{poly_str}}
 *
 * Generated by crcgen.py
 *
 * {{cmdline}}
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
{%- if load %}
    input  wire crc_load,
    input  wire [{{w-1}}:0] crc_in,
{%- endif %}
    output wire [{{sw-1}}:0] crc_out
{%- else %}
    input  wire [{{dw-1}}:0] data_in,
    input  wire [{{w-1}}:0] crc_state,
    output wire [{{sw-1}}:0] crc_next
{%- endif %}
);
{% if not bare %}
reg [{{sw-1}}:0] crc_state;
wire crc_next;

assign crc_out = crc_state;
{% endif -%}
{%- for p in range(sw) %}
assign crc_next[{{p}}] = {% if crc_next[p][0]|length == 0 and crc_next[p][1]|length == 0 -%}0{% else %}
        {%- for i in crc_next[p][0] %}{% if not loop.first %} ^ {% endif %}crc_state[{{i}}]{% endfor %}
        {%- for i in crc_next[p][1] %}{% if crc_next[p][0]|length != 0 or not loop.first %} ^ {% endif %}data_in[{{i}}] {%- endfor %}{% endif %};
{%- endfor %}

{% if not bare -%}
always @(posedge clk or posedge rst) begin
    if (rst) begin
        crc_state <= {{sw}}'h{{'%x' % init2}};
    end else begin
        if (crc_init) begin
            crc_state <= {{sw}}'h{{'%x' % init2}};
{%- if load %}
        end else if (crc_load) begin
            crc_state <= crc_in;
{%- endif %}
        end else if (data_in_valid) begin
            crc_state <= crc_next;
        end
    end
end

{% endif -%}
endmodule

""")
    
    output_file.write(t.render(
        w=width,
        sw=state_width,
        dw=datawidth,
        poly=poly,
        init=init,
        init2=init2,
        poly_str=poly_str,
        crc_next=crc_next,
        load=load,
        bare=bare,
        config=config,
        extend=extend,
        reverse=reverse,
        name=name,
        cmdline=cmdline
    ))

    print("Done")
    

if __name__ == "__main__":
    main()

