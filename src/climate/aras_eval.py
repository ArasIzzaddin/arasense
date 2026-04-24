import numpy as np
import pandas as pd
import plotly.graph_objects as go
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from matplotlib.lines import Line2D
import io

class ArasDiagram:
    """
    Implementation of the Aras Diagram (Izzaddin et al., 2024)
    Refined with R-Theoretical style logic.
    """
    
    def __init__(self, reference_data, model_data, model_names=None):
        self.ref = np.array(reference_data)
        self.models = [np.array(m) for m in model_data]
        self.model_names = model_names if model_names else [f"Model {i+1}" for i in range(len(model_data))]
        
        self.ref_mean = np.mean(self.ref)
        self.ref_std = np.std(self.ref)
        
        self.results = []
        self._calculate_metrics()

    def _calculate_metrics(self):
        for name, m_data in zip(self.model_names, self.models):
            m_mean = np.mean(m_data)
            m_std = np.std(m_data)
            r = np.corrcoef(self.ref, m_data)[0, 1]
            
            # Aras metrics (R-style normalization)
            alpha = (m_mean / self.ref_mean) - 1
            beta = (m_std / self.ref_std) - 1
            
            # KGE and MKGE components
            kge = 1 - np.sqrt((r - 1)**2 + alpha**2 + beta**2)
            mkge = np.abs(kge - 1)
            el = np.sqrt(alpha**2 + beta**2)
            mmkge = mkge - el
            
            # Projected points (x2, y2)
            if el > 0.0001:
                x2 = alpha + mmkge * (alpha / el)
                y2 = beta + mmkge * (beta / el)
            else:
                x2, y2 = alpha, beta
                
            print(f"{name}: α={alpha:.4f}, β={beta:.4f}, r={r:.4f}, x2={x2:.4f}, y2={y2:.4f}")
            
            self.results.append({
                'name': name,
                'alpha': alpha,
                'beta': beta,
                'r': r,
                'kge': kge,
                'mkge': mkge,
                'el': el,
                'x2': x2,
                'y2': y2,
                'e_total': mkge * 100 # Total percentage error
            })

    def plot_r_style(self):
        """Matplotlib implementation matching R-theoretical style."""
        fig, ax = plt.subplots(figsize=(12, 12), facecolor='none')
        ax.set_facecolor('none')
        
        # Calculate limits based on data
        all_vals = []
        for res in self.results:
            all_vals.extend([res['alpha'], res['beta'], res['x2'], res['y2']])
        lim = max(max([abs(v) for v in all_vals]) * 1.2, 0.5)
        
        # Reference Circles
        for rad in [0.1, 0.2, 0.3, 0.4, 0.5]:
            ax.add_patch(Circle((0, 0), rad, color='white', fill=False, linestyle=':', alpha=0.3))
            ax.text(rad, 0.02, f'{int(rad*100)}%', color='white', alpha=0.5, fontsize=10)

        # Plot Segments and Points
        cmap = plt.get_cmap('tab20')
        for i, res in enumerate(self.results):
            color = cmap(i % 20)
            
            # Line connecting (x2, y2) to (alpha, beta)
            ax.plot([res['x2'], res['alpha']], [res['y2'], res['beta']], 
                    color=color, linestyle='-', alpha=0.8, linewidth=3)
            
            # Point (x2, y2) - Combined KGE point (X marker in different style)
            ax.scatter(res['x2'], res['y2'], color='yellow', s=200, marker='X', 
                      edgecolors='orange', linewidths=2, zorder=6)
            
            # Point (alpha, beta) - Bias-Variability point (circle - WHITE edge)
            ax.scatter(res['alpha'], res['beta'], color='none', s=300, 
                      edgecolors='white', linewidths=3, zorder=5)
            ax.scatter(res['alpha'], res['beta'], color=color, s=200, 
                      edgecolors=color, linewidths=2, zorder=6)
            
            # Label
            ax.text(res['alpha'], res['beta'], f" {res['name']}", color='white', 
                   fontsize=10, fontweight='bold', alpha=0.9)

        # Formatting
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)
        ax.axhline(0, color='white', lw=1.5, alpha=0.5)
        ax.axvline(0, color='white', lw=1.5, alpha=0.5)
        
        ax.set_xlabel('Bias ratio - 1 (α)', fontsize=14, color='white', fontweight='bold')
        ax.set_ylabel('Variability ratio - 1 (β)', fontsize=14, color='white', fontweight='bold')
        
        # Custom Legend
        legend_elements = [
            Line2D([0], [0], marker='o', color='gray', label='(α, β) - Bias + Variability', 
                   markersize=12, linestyle='None', markeredgecolor='white'),
            Line2D([0], [0], marker='X', color='gray', label='(x₂, y₂) - Combined KGE', 
                   markersize=12, linestyle='None', markeredgecolor='white'),
            Line2D([0], [0], color='gray', linestyle='-', linewidth=3, label='Correlation Influence')
        ]
        leg = ax.legend(handles=legend_elements, loc='upper right', fontsize=11, 
                       facecolor='#1a1a1a', edgecolor='white', framealpha=0.9)
        for text in leg.get_texts():
            text.set_color('white')

        ax.grid(True, linestyle='--', alpha=0.1)
        plt.tight_layout()
        
        return fig

    def plot(self):
        """Maintain Plotly version for interactivity if needed."""
        fig = go.Figure()
        # Origin
        fig.add_trace(go.Scatter(x=[0], y=[0], mode='markers', marker=dict(size=12, color='white', symbol='cross'), name='Reference'))
        
        for res in self.results:
            # Segment
            fig.add_trace(go.Scatter(x=[res['x2'], res['alpha']], y=[res['y2'], res['beta']], mode='lines', line=dict(width=1, color='rgba(255,255,255,0.3)'), showlegend=False))
            # Main point
            fig.add_trace(go.Scatter(x=[res['alpha']], y=[res['beta']], mode='markers+text', name=res['name'], text=[res['name']], textposition="bottom center", marker=dict(size=10)))
            
        fig.update_layout(template="plotly_dark", xaxis_title="α", yaxis_title="β", width=800, height=800)
        return fig
