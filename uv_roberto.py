"""
Creazione: Thu Jul 23 14:54:47 2026
Autore: daniele.carnevale
"""

import os
import sys
import ast
import configparser
import warnings
warnings.filterwarnings('ignore', category=UserWarning)

import locale
locale.setlocale(locale.LC_TIME, 'it_IT.UTF-8')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import matplotlib.image as mpimg
from matplotlib.collections import LineCollection
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from scipy.interpolate import make_interp_spline
from datetime import datetime, timezone

sys.path.insert(0, os.path.expanduser('~/.config'))
from config_percorsi_Daniele import CARTELLA_REPO_ROOT

cartella_lavoro = os.path.join(CARTELLA_REPO_ROOT, 'uv_roberto')
os.chdir(cartella_lavoro)

from matplotlib import font_manager
font_files = font_manager.findSystemFonts(fontpaths='NotoSansNerdFont')
for font_file in font_files:
    font_manager.fontManager.addfont(font_file)

plt.rc('font', family=font_manager.FontProperties(fname=font_file).get_name(), weight='normal', size=10)

from danilib import f_settaggio_db_arpal
connessione = f_settaggio_db_arpal()

# config = configparser.ConfigParser()
# config.read('./config.ini')

def get_colore(valore, dict_colori):
    for colore, (lo, hi) in dict_colori.items():
        if lo <= valore <= hi:
            return colore
    return 'gray'

def formatta_tick(x, pos):
    data = mdates.num2date(x)
    if data.hour == 0:
        return data.strftime('%a\n%d %b')
    elif data.hour in [3, 9, 15, 21]:
        return ''
    else:
        return data.strftime('%H:00')
    
# %%
# for delay in np.arange(0, 14, 1):
#     for m in [0, 30]:
        # adesso_timestamp = pd.to_datetime(datetime.now(timezone.utc)).tz_localize(None).floor('30min') - pd.Timedelta(hours=delay) - pd.Timedelta(minutes=m)

adesso_timestamp = pd.to_datetime(datetime.now(timezone.utc)).tz_localize(None).floor('30min')

gg3 = adesso_timestamp - pd.Timedelta(hours=72)

adesso = adesso_timestamp.strftime('%Y%m%d%H%M')
gg3 = gg3.strftime('%Y%m%d%H%M')

print(adesso_timestamp)

query = f"""
SELECT
    DATA.CODE,
    DATA.DTRF,
    ANAG.NAME,
    UVINDM / 100 as UV_MEDIA,
    UVINDX / 100 as UV_MASSIMA
FROM
    DATA, ANAG
WHERE
    DATA.CODE = ANAG.CODE AND
    DATA.DTRF > TO_DATE('{gg3}', 'YYYYMMDDHH24MI') AND
    DATA.DTRF <= TO_DATE('{adesso}', 'YYYYMMDDHH24MI')
    AND DATA.CODE IN ('CFUNZ', 'SPZIA')
    AND TO_CHAR(DATA.DTRF, 'MI') IN ('00', '30')
ORDER BY DATA.DTRF
"""

df_query = pd.read_sql(query, con=connessione)

dizionario_df = {
    code: gruppo[['DTRF', 'NAME', 'UV_MEDIA', 'UV_MASSIMA']]
        .assign(DTRF=lambda d: d['DTRF'].dt.tz_localize('UTC').dt.tz_convert('Europe/Rome').dt.tz_localize(None))
        .set_index('DTRF').rename_axis('')
    for code, gruppo in df_query.groupby('CODE')
}
del (df_query)

# %%

# Palette -> https://www.sciencedirect.com/science/article/pii/S2666469023000210

dict_colori = {
    '#97D700': [0, 2.50],
    '#FCE300': [2.50, 5.50],
    '#FF8200': [5.50, 7.50],
    '#EF3340': [7.50, 10.50],
    '#9063CD': [10.50, 15],
    }

# for stazione in dizionario_df.keys():
for stazione in ['CFUNZ']:
    cartella_plot = f"plot/{stazione}/{adesso_timestamp.strftime('%Y/%m/%d')}"
    os.makedirs(cartella_plot, exist_ok=True)
    
    df = dizionario_df[stazione]
    df = df.fillna(0)
    nome = df.iloc[0]['NAME']
    df = df['UV_MEDIA'].to_frame()
    # df = (df.resample('10min').interpolate('linear'))
    
    ##############
    
    fig, ax = plt.subplots(figsize=(10, 5))
    
    ### barre
    # width = df.index.to_series().diff().median().total_seconds() / 86400
    # colori_barre = df['UV_MEDIA'].apply(lambda v: get_colore(v, dict_colori))

    # ax.bar(
    #     df.index,
    #     df['UV_MEDIA'],
    #     width=width,
    #     color=colori_barre,
    #     align='edge',
    #     alpha=1,
    #     edgecolor='black',
    #     linewidth=0.01,
    #     zorder=10
    #     )
    
    ### linea continua
    
    x_smooth_totale = []
    y_smooth_totale = []
    
    id_blocco = (df['UV_MEDIA'] == 0).cumsum()
    for _, blocco in df[df['UV_MEDIA'] > 0].groupby(id_blocco):
        if len(blocco) < 3:
            continue
        x_num = mdates.date2num(blocco.index)
        y = blocco['UV_MEDIA'].values
        
        grado = min(3, len(blocco) - 1)
        spline = make_interp_spline(x_num, y, k=grado)
        x_smooth = np.linspace(x_num.min(), x_num.max(), len(blocco) * 10)
        y_smooth = np.clip(spline(x_smooth), 0, None)
        
        x_smooth_totale.append(x_smooth)
        y_smooth_totale.append(y_smooth)
        
        punti = np.array([x_smooth, y_smooth]).T.reshape(-1, 1, 2)
        segmenti = np.concatenate([punti[:-1], punti[1:]], axis=1)
        colori_segmenti = [get_colore(v, dict_colori) for v in y_smooth[:-1]]
        
        for i in range(len(x_smooth) - 1):
            colore_medio = get_colore((y_smooth[i] + y_smooth[i + 1]) / 2, dict_colori)
            ax.fill_between(
                x_smooth[i:i + 2], y_smooth[i:i + 2], 0,
                color=colore_medio, alpha=1, zorder=5,
                edgecolor='none', linewidth=0, antialiased=False
                )
        
        lc = LineCollection(segmenti, colors=colori_segmenti, linewidth=0, zorder=10)
        ax.add_collection(lc)
    
    x_smooth_totale = np.concatenate(x_smooth_totale) if x_smooth_totale else np.array([])
    y_smooth_totale = np.concatenate(y_smooth_totale) if y_smooth_totale else np.array([])
    
    ######################
    
    for colore, valori in list(dict_colori.items())[1:]:
        ax.axhline(y=valori[0], color=colore, linestyle='--', linewidth=0.8, zorder=-10, alpha=0.9)
    
    ax.set_xlabel('')
    ax.set_ylabel('Indice UV')
    ax.set_title(nome)
    ax.margins(x=0)
    ax.set_xlim(df.index.min(), df.index.max())
    ax.set_ylim(0, 9.5)
    ax.set_yticks(range(1, 10))
    ax.tick_params(axis='x', labelsize=8)
    
    ax.xaxis.set_major_locator(mdates.HourLocator(byhour=range(0, 24, 3)))
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(formatta_tick))
    
    fig.canvas.draw()
    xlim_max = ax.get_xlim()[1]
    ultima_label_visibile = None
    for tick_pos, label in zip(ax.get_xticks(), ax.get_xticklabels()):
        if tick_pos <= xlim_max:
            ultima_label_visibile = label
    if ultima_label_visibile is not None:
        ultima_label_visibile.set_visible(False)
    
    ax.grid(axis='y', linestyle='--', alpha=0.2, linewidth=0.6, zorder=-10)
    
    for xc in df.index[(df.index.hour == 0) & (df.index.minute == 0)]:
        ax.axvline(x=xc, color='gray', linestyle='-', linewidth=0.6, alpha=0.4, zorder=-100)
    
    plt.tight_layout()
    
    ################
    
    logo = mpimg.imread(os.path.join(cartella_lavoro, 'arpal.png'))
    imagebox = OffsetImage(logo, zoom=0.25)
    ab = AnnotationBbox(
        imagebox,
        (0.99, 0.99),
        xycoords='axes fraction',
        frameon=True,
        box_alignment=(1, 1),
        bboxprops=dict(facecolor='white', edgecolor='none', alpha=0.8)
        )
    ax.add_artist(ab)
    
    def valore_curva(x):
        if len(x_smooth_totale) == 0:
            return np.zeros_like(np.atleast_1d(x), dtype=float)
        return np.interp(x, x_smooth_totale, y_smooth_totale, left=0, right=0)
    
    massimi_giorno = []
    for giorno, gruppo_giorno in df.groupby(df.index.date):
        if gruppo_giorno['UV_MEDIA'].max() == 0:
            continue
        val_max = gruppo_giorno['UV_MEDIA'].max()
        target = pd.Timestamp(giorno) + pd.Timedelta(hours=13) + pd.Timedelta(minutes=30)
        
        if target in gruppo_giorno.index:
            x_pos = target
        else:
            tempi_dopo = gruppo_giorno.index[gruppo_giorno.index > target]
            tempi_prima = gruppo_giorno.index[gruppo_giorno.index < target]
            if len(tempi_prima) == 0 and len(tempi_dopo) > 0:
                x_pos = tempi_dopo.min()
            elif len(tempi_dopo) == 0 and len(tempi_prima) > 0:
                x_pos = tempi_prima.max()
            else:
                continue
        
        val_locale = gruppo_giorno.loc[x_pos, 'UV_MEDIA']
        massimi_giorno.append((mdates.date2num(x_pos), val_max, val_locale))
    
    x_min_asse, x_max_asse = mdates.date2num(df.index.min()), mdates.date2num(df.index.max())
    pad_dati = (x_max_asse - x_min_asse) * 0.035
    
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    
    for x_pos, val_max, val_locale in massimi_giorno:
        y_box = max(7.15, val_locale + 0.5)
        colore_box = get_colore(val_max, dict_colori)
        txt = ax.text(
            x_pos, y_box, int(np.ceil(val_max)),
            fontsize=10, fontweight='bold', zorder=200,
            ha='left', va='center_baseline', color='white',
            bbox=dict(boxstyle='round,pad=0.3', facecolor=colore_box, edgecolor='none')
            )
        
        bbox_dati = txt.get_window_extent(renderer=renderer).transformed(ax.transData.inverted())
        larghezza_box = bbox_dati.x1 - bbox_dati.x0
        
        x_finale = x_pos
        if bbox_dati.x1 > x_max_asse:
            x_finale = x_max_asse - larghezza_box - pad_dati
        elif bbox_dati.x0 < x_min_asse:
            x_finale = x_min_asse + pad_dati
        
        x_span = np.linspace(x_finale, x_finale + larghezza_box, 10)
        y_box = max(7.15, valore_curva(x_span).max() + 0.5)
        
        txt.set_position((x_finale, y_box))
    
    for spine in ax.spines.values():
        spine.set_zorder(200)
        
    percorso_plot = f"{cartella_plot}/{adesso_timestamp.strftime('%Y-%m-%d_%H%M')}.png"
    plt.savefig(percorso_plot, dpi=300, bbox_inches='tight')
    os.system(f'convert {percorso_plot} -strip -colors 32 PNG8:{percorso_plot}')
    
    plt.show()
    plt.close()
    
    # sss

print('\n\nDone.')
