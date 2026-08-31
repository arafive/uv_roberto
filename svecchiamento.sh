#!/bin/bash
# svecchiamento_plot.sh - cancella PNG più vecchi di 3 giorni in /plot

DIR="/home/cfmi.arpal.org/meteo/uv_roberto/plot"

# Cancella i file PNG con mtime > 3 giorni
find "$DIR" -type f -name "*.png" -mtime +3 -print -delete

# Rimuove le sottocartelle rimaste vuote (esclude la root)
find "$DIR" -mindepth 1 -type d -empty -delete

