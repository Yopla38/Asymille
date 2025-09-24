import tkinter as tk
from tkinter import filedialog
import numpy as np
import lmfit
from scipy.integrate import quad
from numba import jit
import plotly.graph_objects as go
from plotly.subplots import make_subplots


@jit(nopython=True)
def W(r, Wmax):
    """Taux de recombinaison en fonction de la distance normalisée
    Args:
        r (float): Distance normalisée
        Wmax (float): Taux de recombinaison maximal
    Returns:
        float: Taux de recombinaison
    """
    return Wmax * np.exp(-r ** 2)


def integral1(t, Wmax):
    """Première intégrale du modèle
    Args:
        t (float): Temps
        Wmax (float): Taux de recombinaison maximal
    Returns:
        float: Valeur de l'intégrale
    """

    def integrand(r):
        w_val = W(r, Wmax)
        return w_val * np.exp(-w_val * t) * r

    return quad(integrand, 0, 5.0, limit=100, epsabs=1e-4, epsrel=1e-4)[0]


def integral2(t, Wmax):
    """Deuxième intégrale du modèle
    Args:
        t (float): Temps
        Wmax (float): Taux de recombinaison maximal
    Returns:
        float: Valeur de l'intégrale
    """

    def integrand(r):
        return np.exp(-W(r, Wmax) * t) - 1

    return quad(integrand, 0, 5.0, limit=100, epsabs=1e-4, epsrel=1e-4)[0]


def intensity_vectorized(times, eta, Wmax):
    """Calcul de l'intensité pour tous les temps
    Args:
        times (array): Temps
        eta (float): Paramètre eta (n*a²)
        Wmax (float): Taux de recombinaison maximal
    Returns:
        array: Intensités calculées
    """
    results = np.zeros_like(times)
    for i, t in enumerate(times):
        int1 = integral1(t, Wmax)
        int2 = integral2(t, Wmax)
        results[i] = 2 * np.pi * eta * int1 * np.exp(2 * np.pi * eta * int2)
    return results


def open_file():
    """Ouvre une boîte de dialogue pour sélectionner un fichier"""
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(filetypes=[("Fichiers DAT", "*.dat")])
    root.destroy()
    return file_path


def process_data(file_path, decay: float = 13.75):
    """Lit, normalise et filtre les données du fichier"""
    data = np.loadtxt(file_path, skiprows=10)
    data_normalized = data / np.max(data)
    time_step = 0.004
    times = np.arange(len(data)) * time_step
    min_time, max_time = 13.75, 18.75
    mask = (times >= min_time) & (times <= max_time)

    step = 2  # Sous-échantillonnage
    filtered_times = times[mask][::step]
    # Décalage des temps de -13.75
    filtered_times = filtered_times - decay
    filtered_counts = data_normalized[mask][::step]
    return filtered_times, filtered_counts


def fit_with_analytical(times, counts):
    """Réalise l'ajustement du modèle aux données
    Args:
        times (array): Temps
        counts (array): Intensités mesurées
    Returns:
        lmfit.MinimizerResult: Résultat de l'ajustement
    """
    def objective(params):
        eta = params['eta'].value
        Wmax = params['Wmax'].value
        model = intensity_vectorized(times, eta, Wmax)
        return model - counts

    # Paramètres initiaux
    params = lmfit.Parameters()
    params.add('eta', value=1.0, min=0.1, max=10.0)
    params.add('Wmax', value=1.0, min=0.1, max=5.0)

    # Ajustement
    min_result = lmfit.minimize(objective, params, method='leastsq')
    print(lmfit.fit_report(min_result))

    # Calcul du modèle ajusté
    eta_fit = min_result.params['eta'].value
    Wmax_fit = min_result.params['Wmax'].value
    model_fit = intensity_vectorized(times, eta_fit, Wmax_fit)

    # Visualisation
    create_plotly_figure(times, counts, model_fit,
                        {'eta': eta_fit, 'Wmax': Wmax_fit})

    return min_result


def create_plotly_figure(times, counts, model_fit, params):
    """Crée la figure avec les données et l'ajustement
    Args:
        times (array): Temps
        counts (array): Intensités mesurées
        model_fit (array): Modèle ajusté
        params (dict): Paramètres d'ajustement
    """
    # Calcul des résidus
    residuals = counts - model_fit

    # Création de la figure
    fig = make_subplots(rows=2, cols=1,
                        row_heights=[0.7, 0.3],
                        vertical_spacing=0.15,
                        subplot_titles=('Ajustement de la courbe de déclin',
                                        'Résidus'))

    # Données expérimentales
    fig.add_trace(
        go.Scatter(x=times, y=counts,
                   mode='markers',
                   name='Données',
                   marker=dict(size=6, color='blue')),
        row=1, col=1
    )

    # Ajustement
    fig.add_trace(
        go.Scatter(x=times, y=model_fit,
                   mode='lines',
                   name='Ajustement',
                   line=dict(color='red')),
        row=1, col=1
    )

    # Résidus
    fig.add_trace(
        go.Scatter(x=times, y=residuals,
                   mode='markers',
                   name='Résidus',
                   marker=dict(size=6, color='green')),
        row=2, col=1
    )

    # Mise en page
    fig.update_layout(
        title_text=f"η={params['eta']:.3f}, Wmax={params['Wmax']:.3f}",
        height=800,
        showlegend=True,
        yaxis_type="log"
    )

    fig.show()


def main():
    # Sélection du fichier
    file_path = "/home/yopla/Downloads/N3978_shutter_diaph2mm_3kV_spot3_int200s_236nm_160K.dat"

    if file_path:
        try:
            # Traitement des données
            filtered_times, filtered_counts = process_data(file_path)

            # Ajustement
            fit_with_analytical(filtered_times, filtered_counts)

        except Exception as e:
            print(f"Erreur lors du traitement : {e}")


if __name__ == "__main__":
    main()