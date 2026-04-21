import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from matplotlib.lines import Line2D

def generate_aras_diagram_v2(csv_file):
    # 1. Load the basin-specific results
    df = pd.read_csv(csv_file)
    
    # 2. Re-calculate metrics following the R script logic
    # Bias_ratio = mean_sim / mean_obs - 1  (This is our 'alpha')
    # Variability_ratio = std_sim / std_obs - 1 (This is our 'beta')
    # Mkge = abs(KGE - 1)
    # el = sqrt(Bias_ratio^2 + Variability_ratio^2)
    # mmkge = Mkge - el
    # x2 = Bias_ratio + mmkge * (Bias_ratio/el)
    # y2 = Variability_ratio + mmkge * (Variability_ratio/el)
    
    # In my CSV: alpha = (mean_sim - mean_obs)/mean_obs = mean_sim/mean_obs - 1. CORRECT.
    # In my CSV: beta = (std_sim - std_obs)/std_obs = std_sim/std_obs - 1. CORRECT.
    
    # Need to calculate KGE for each model to get Mkge
    # Note: KGE = 1 - sqrt((r-1)^2 + (mean_sim/mean_obs - 1)^2 + (std_sim/std_obs - 1)^2)
    # This matches: 1 - sqrt((r-1)^2 + alpha^2 + beta^2)
    
    df['kge'] = 1 - np.sqrt((df['r'] - 1)**2 + df['alpha']**2 + df['beta']**2)
    df['Mkge'] = np.abs(df['kge'] - 1)
    df['el'] = np.sqrt(df['alpha']**2 + df['beta']**2)
    df['mmkge'] = df['Mkge'] - df['el']
    
    # Handle el=0 to avoid division by zero
    df['x2'] = df['alpha'] + df['mmkge'] * (df['alpha'] / df['el'].replace(0, np.nan))
    df['y2'] = df['beta'] + df['mmkge'] * (df['beta'] / df['el'].replace(0, np.nan))
    df.loc[df['el'] == 0, ['x2', 'y2']] = 0
    
    # 3. Setup Plot
    fig, ax = plt.subplots(figsize=(14, 14))
    
    # Calculate limits
    lim = max(pd.concat([df['alpha'], df['beta'], df['x2'], df['y2']]).abs().max() * 1.2, 0.5)
    
    # 4. Reference Circles
    for r in [0.1, 0.2, 0.3, 0.4, 0.5]:
        ax.add_patch(Circle((0, 0), r, color='lightgray', fill=False, linestyle=':', alpha=0.5))
        ax.text(r, 0.02, f'{int(r*100)}%', color='gray', alpha=0.5, fontsize=10)

    # 5. Plot Origin
    ax.scatter(0, 0, marker='+', color='black', s=200, zorder=10)

    # 6. Plot Segments and Points (R-style)
    # In R: geom_segment(aes(x = x2, y = y2, xend = Bias_ratio, yend = Variability_ratio))
    # Bias_ratio is alpha, Variability_ratio is beta
    
    cmap = plt.colormaps.get_cmap('tab20')
    
    for i, row in df.iterrows():
        color = cmap(i % 20)
        
        # Segment from (x2, y2) to (alpha, beta)
        ax.plot([row['x2'], row['alpha']], [row['y2'], row['beta']], 
                color=color, linestyle='-', alpha=0.6, linewidth=1.5)
        
        # Point (alpha, beta) - Bias/Variability
        # R uses geom_point(aes(x = Bias_ratio, y = Variability_ratio))
        ax.scatter(row['alpha'], row['beta'], color=color, s=100, label=row['model_id'] if i < 10 else "", alpha=0.8)
        
        # Point (x2, y2) - The "Projected" Error point incorporating correlation
        # R uses geom_point(aes(x = x2, y = y2))
        ax.scatter(row['x2'], row['y2'], color=color, s=50, marker='x', alpha=0.6)

    # 7. Formatting
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.axhline(0, color='black', lw=1)
    ax.axvline(0, color='black', lw=1)
    ax.set_xlabel('Bias ratio - 1 (α)', fontsize=14, fontweight='bold')
    ax.set_ylabel('Variability ratio - 1 (β)', fontsize=14, fontweight='bold')
    ax.set_title('Aras Diagram: Fiumarella Basin (R-Theoretical Implementation)\n55 EURO-CORDEX Models Evaluation', 
                 fontsize=16, pad=20)
    
    # Custom Legend
    legend_elements = [
        Line2D([0], [0], marker='o', color='gray', label='Bias-Variability (α, β)', markersize=10, linestyle='None'),
        Line2D([0], [0], marker='x', color='gray', label='Combined KGE Point (x2, y2)', markersize=8, linestyle='None'),
        Line2D([0], [0], color='gray', linestyle='-', label='Correlation Influence Segment')
    ]
    ax.legend(handles=legend_elements, loc='lower left', fontsize=12)

    plt.grid(True, linestyle='--', alpha=0.3)
    plt.tight_layout()
    plt.savefig('fig_aras_diagram_R_style.png', dpi=300)
    print("R-style Aras Diagram saved as fig_aras_diagram_R_style.png")

if __name__ == "__main__":
    generate_aras_diagram_v2('aras_cordex_basin_results.csv')
