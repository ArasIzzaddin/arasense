import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from matplotlib.lines import Line2D
from scipy import stats


class ArasDiagram:
    """
    Aras Diagram (Izzaddin et al., 2024)
    
    Construction:
        α     = mean_sim / mean_obs - 1       bias component
        β     = std_sim  / std_obs  - 1       variability component
        r     = Pearson correlation
        KGE   = 1 - sqrt((r-1)² + α² + β²)
        Mkge  = |KGE - 1|
        el    = sqrt(α² + β²)
        mmkge = Mkge - el
        x2    = α + mmkge × (α / el)          Aras x-coordinate
        y2    = β + mmkge × (β / el)          Aras y-coordinate
    
    Visualization:
        - Point (α, β)       = pure bias + variability error
        - Point (x2, y2)     = full error including correlation
        - Segment (x2,y2)→(α,β) = correlation influence
        - Perfect model → (x2=0, y2=0)
    """
    
    def __init__(self, reference_data, model_data, model_names=None):
        self.ref = np.array(reference_data)
        self.models = [np.array(m) for m in model_data]
        self.model_names = model_names if model_names else [f"Model {i+1}" for i in range(len(model_data))]
        
        self.results = []
        self._calculate_metrics()

    def _calculate_metrics(self):
        """Compute Aras metrics for each model."""
        for name, m_data in zip(self.model_names, self.models):
            result = compute_aras(self.ref, m_data)
            result['name'] = name
            self.results.append({
                'name': name,
                'alpha': result['alpha'],
                'beta': result['beta'],
                'r': result['r'],
                'kge': result['KGE'],
                'mkge': result['Mkge'],
                'el': result['el'],
                'x2': result['x2'],
                'y2': result['y2'],
                'e_total': result['Mkge'] * 100
            })

    def plot_r_style(self):
        """Publication-quality Aras diagram."""
        fig, ax = plt.subplots(figsize=(12, 12), facecolor='white')
        
        # Data bounds
        all_vals = []
        for res in self.results:
            all_vals.extend([res['alpha'], res['beta'], res['x2'], res['y2']])
        
        max_val = max(0.5, max(abs(v) for v in all_vals if not np.isnan(v))) * 1.3
        lim = max_val
        
        # Reference circles (KGE distance from origin)
        for radius in [0.25, 0.50, 0.75, 1.0, 1.25]:
            circle = Circle((0, 0), radius, color='lightgray',
                           fill=False, linestyle=':', linewidth=0.8, alpha=0.6)
            ax.add_patch(circle)
            ax.text(radius + 0.02, 0.02, f'{radius:.2f}',
                   color='gray', fontsize=7, alpha=0.7)

        # Axes
        ax.axhline(0, color='black', linewidth=0.8, zorder=1)
        ax.axvline(0, color='black', linewidth=0.8, zorder=1)
        
        # Origin marker (perfect model)
        ax.scatter(0, 0, marker='+', color='black', s=150, zorder=10, linewidths=2)
        
        # Plot each model
        colors = plt.cm.tab10(np.linspace(0, 1, len(self.results)))
        
        for i, res in enumerate(self.results):
            if any(np.isnan([res['alpha'], res['beta'], res['x2'], res['y2']])):
                continue
            
            color = colors[i]
            
            # Segment: (x2,y2) → (α,β) — correlation influence
            ax.plot([res['x2'], res['alpha']],
                   [res['y2'], res['beta']],
                   color=color, linestyle='-',
                   alpha=0.8, linewidth=2, zorder=2)
            
            # Point (α, β) — pure bias+variability (larger, white edge)
            ax.scatter(res['alpha'], res['beta'],
                      color=color, s=120,
                      edgecolors='white', linewidths=2,
                      zorder=3)
            
            # Point (x2, y2) — full error (smaller, x marker)
            ax.scatter(res['x2'], res['y2'],
                      color=color, s=60,
                      marker='x', alpha=0.7, zorder=4,
                      linewidths=1.5)
            
            # Label at (α, β)
            ax.annotate(res['name'],
                       (res['alpha'], res['beta']),
                       textcoords='offset points',
                       xytext=(8, 8), fontsize=9,
                       color='black',
                       fontweight='bold')

        # Axis labels
        ax.set_xlabel("Bias ratio − 1  (α)", fontsize=12, fontweight='bold')
        ax.set_ylabel("Variability ratio − 1  (β)", fontsize=12, fontweight='bold')
        
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)
        ax.set_aspect('equal')
        ax.grid(True, linestyle='--', alpha=0.2)
        
        # Legend
        legend_elements = [
            Line2D([0], [0], marker='o', color='gray',
                  label='(α, β) — bias + variability',
                  markersize=10, linestyle='None',
                  markeredgecolor='white', markeredgewidth=2),
            Line2D([0], [0], marker='x', color='gray',
                  label='(x₂, y₂) — full error',
                  markersize=8, linestyle='None'),
            Line2D([0], [0], color='gray', linestyle='-',
                  label='Correlation influence',
                  linewidth=2),
            Line2D([0], [0], marker='+', color='black',
                  label='Perfect model (origin)',
                  markersize=12, linestyle='None'),
        ]
        ax.legend(handles=legend_elements,
                 loc='upper left',
                 fontsize=10,
                 framealpha=0.9)
        
        plt.tight_layout()
        return fig


def compute_aras(obs, sim):
    """
    Compute Aras diagram metrics.
    
    Parameters
    ----------
    obs : array — observed values
    sim : array — simulated values (same length as obs)
    
    Returns
    -------
    dict with keys: alpha, beta, r, pval, KGE, Mkge, el, mmkge, x2, y2
    """
    # Remove NaN pairs
    mask = np.isfinite(obs) & np.isfinite(sim)
    obs = np.array(obs)[mask]
    sim = np.array(sim)[mask]
    
    n = len(obs)
    if n < 3:
        return {k: np.nan for k in ['alpha', 'beta', 'r', 'pval', 'KGE', 'Mkge', 'el', 'mmkge', 'x2', 'y2']}
    
    # Statistics
    mu_obs = np.mean(obs)
    mu_sim = np.mean(sim)
    std_obs = np.std(obs, ddof=1)
    std_sim = np.std(sim, ddof=1)
    
    # α: bias ratio (0 = perfect, >0 = wet bias, <0 = dry bias)
    alpha = (mu_sim / mu_obs) - 1 if mu_obs != 0 else np.nan
    
    # β: variability ratio
    beta = (std_sim / std_obs) - 1 if std_obs != 0 else np.nan
    
    # Pearson correlation
    if std_obs > 0 and std_sim > 0:
        r, pval = stats.pearsonr(obs, sim)
    else:
        r, pval = np.nan, np.nan
    
    # KGE = 1 - sqrt((r-1)² + α² + β²)
    KGE = 1 - np.sqrt((r - 1)**2 + alpha**2 + beta**2)
    
    # Mkge = |KGE - 1|
    Mkge = abs(KGE - 1)
    
    # el = sqrt(α² + β²) — distance from origin
    el = np.sqrt(alpha**2 + beta**2)
    
    # mmkge = Mkge - el — correlation influence
    mmkge = Mkge - el
    
    # Final Aras coordinates
    if el != 0:
        x2 = alpha + mmkge * (alpha / el)
        y2 = beta + mmkge * (beta / el)
    else:
        x2, y2 = 0.0, 0.0  # perfect model at origin
    
    return {
        'alpha': float(alpha),
        'beta': float(beta),
        'r': float(r),
        'pval': float(pval),
        'KGE': float(KGE),
        'Mkge': float(Mkge),
        'el': float(el),
        'mmkge': float(mmkge),
        'x2': float(x2),
        'y2': float(y2),
    }