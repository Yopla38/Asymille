import xml.etree.ElementTree as ET
import numpy as np


def convert_specan_file(input_filename, output_filename):
    # Lecture du fichier XML
    tree = ET.parse(input_filename)
    root = tree.getroot()

    # Extraction des données
    waveform = root.find('.//Waveform')

    # Récupération des paramètres
    x_start = float(waveform.find('XStart').text)
    x_stop = float(waveform.find('XStop').text)
    count = int(waveform.find('Count').text)

    # Création du vecteur x en kHz
    x = np.linspace(x_start, x_stop, count) / 1000  # Conversion en kHz

    # Récupération des valeurs y en dBm
    y_dbm = [float(y.text) for y in waveform.findall('y')]

    # Conversion des dBm en Watts
    y_watts = [10 ** ((dbm - 30) / 10) for dbm in y_dbm]

    # Écriture dans le fichier de sortie
    with open(output_filename, 'w') as f:
        f.write("# Frequence(kHz)\tPuissance(W)\n")  # En-tête
        for freq, power in zip(x, y_watts):
            f.write(f"{freq:.6f}\t{power:.6e}\n")

    print(f"Fichier converti et sauvegardé dans {output_filename}")

convert_specan_file('NW1051-NW1.Specan', 'test.txt')