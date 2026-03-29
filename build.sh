#!/bin/bash

pandoc Building-on-Algorand.md -o Building-on-Algorand.pdf --pdf-engine=xelatex --syntax-highlighting=tango --top-level-division=chapter --toc --toc-depth=2 -N
