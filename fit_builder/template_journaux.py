class ScientificTemplates:
    @staticmethod
    def get_templates() -> dict:
        return {
            "nature": {
                "figure": {
                    # Nature recommande:
                    # - Largeur: 89mm (une colonne) ou 183mm (deux colonnes)
                    # - Hauteur: maximum ~230mm
                    # - Ratio typique pour une figure à une colonne: ~1.3
                    "width": 89 * 2.835,  # 89mm en pixels (300 dpi)
                    "height": 69 * 2.835,  # ~69mm pour un ratio agréable
                    "bgcolor": "white",
                    "margin": {"l": 60, "r": 20, "t": 20, "b": 40}
                },
                "font": {
                    "family": "Arial",
                    "size": 8,  # Nature recommande 5-7pt pour les labels
                    "color": "black"
                },
                "xaxis": {
                    "title": {
                        "font": {"size": 8, "family": "Arial"},  # 8pt pour les titres d'axes
                        "standoff": 5
                    },
                    "tickfont": {"size": 7, "family": "Arial"},  # 7pt pour les ticks
                    "showgrid": True,
                    "gridcolor": "#E5E5E5",
                    "gridwidth": 0.5,
                    "linewidth": 0.5,
                    "linecolor": "black",
                    "ticks": "outside",
                    "ticklen": 2,
                    "tickwidth": 0.5,
                    "mirror": True
                },
                "yaxis": {
                    "title": {
                        "font": {"size": 8, "family": "Arial"},
                        "standoff": 5
                    },
                    "tickfont": {"size": 7, "family": "Arial"},
                    "showgrid": True,
                    "gridcolor": "#E5E5E5",
                    "gridwidth": 0.5,
                    "linewidth": 0.5,
                    "linecolor": "black",
                    "ticks": "outside",
                    "ticklen": 2,
                    "tickwidth": 0.5,
                    "mirror": True
                },
                "legend": {
                    "font": {"size": 7, "family": "Arial"},
                    "borderwidth": 0,
                    "yanchor": "top",
                    "y": 0.99,
                    "xanchor": "right",
                    "x": 0.99
                }
            },

            "web": {
               "figure": {
                   "width": 1200,  # Large vue pour écrans modernes
                   "height": 600,  # Ratio 2:1 pour une bonne visualisation
                   "bgcolor": "#FFFFFF",
                   "margin": {
                       "l": 80,
                       "r": 40,
                       "t": 40,
                       "b": 60,
                       "pad": 10
                   }
               },
               "font": {
                   "family": "Roboto, Arial, sans-serif",
                   "size": 14,
                   "color": "#2F3337"
               },
               "xaxis": {
                   "title": {
                       "font": {
                           "family": "Roboto, Arial, sans-serif",
                           "size": 16,
                           "color": "#2F3337"
                       },
                       "standoff": 15
                   },
                   "tickfont": {
                       "family": "Roboto, Arial, sans-serif",
                       "size": 12
                   },
                   "showgrid": True,
                   "gridcolor": "#E1E5EA",
                   "gridwidth": 1,
                   "linewidth": 1,
                   "linecolor": "#2F3337",
                   "ticks": "outside",
                   "ticklen": 5,
                   "tickwidth": 1,
                   "mirror": True,
                   "showline": True
               },
               "yaxis": {
                   "title": {
                       "font": {
                           "family": "Roboto, Arial, sans-serif",
                           "size": 16,
                           "color": "#2F3337"
                       },
                       "standoff": 15
                   },
                   "tickfont": {
                       "family": "Roboto, Arial, sans-serif",
                       "size": 12
                   },
                   "showgrid": True,
                   "gridcolor": "#E1E5EA",
                   "gridwidth": 1,
                   "linewidth": 1,
                   "linecolor": "#2F3337",
                   "ticks": "outside",
                   "ticklen": 5,
                   "tickwidth": 1,
                   "mirror": True,
                   "showline": True
               },
                "legend": {
                    "font": {"size": 7, "family": "Arial"},
                    "borderwidth": 0,
                    "yanchor": "top",
                    "y": 0.99,
                    "xanchor": "right",
                    "x": 0.99
                }
            },

            "science": {  # Science Magazine
                "figure": {
                    "width": 85 * 2.835,  # 85mm en pixels
                    "height": 85 * 2.835,
                    "bgcolor": "white",
                    "margin": {"l": 50, "r": 20, "t": 20, "b": 40}
                },
                "font": {
                    "family": "Arial",
                    "size": 7,
                    "color": "black"
                },
                "xaxis": {
                    "title": {
                        "font": {"size": 8, "family": "Arial"},
                        "standoff": 5
                    },
                    "tickfont": {"size": 7, "family": "Arial"},
                    "showgrid": True,
                    "gridcolor": "#E5E5E5",
                    "gridwidth": 0.5,
                    "linewidth": 0.5,
                    "linecolor": "black",
                    "ticks": "outside",
                    "ticklen": 2,
                    "tickwidth": 0.5,
                    "mirror": True
                },
                "yaxis": {
                    "title": {
                        "font": {"size": 8, "family": "Arial"},
                        "standoff": 5
                    },
                    "tickfont": {"size": 7, "family": "Arial"},
                    "showgrid": True,
                    "gridcolor": "#E5E5E5",
                    "gridwidth": 0.5,
                    "linewidth": 0.5,
                    "linecolor": "black",
                    "ticks": "outside",
                    "ticklen": 2,
                    "tickwidth": 0.5,
                    "mirror": True
                },
                "legend": {
                    "font": {"size": 6, "family": "Arial"},
                    "borderwidth": 0
                }
            },

            "physical_review_letters": {  # PRL
                "figure": {
                    "width": 86 * 2.835,  # 86mm en pixels
                    "height": 86 * 2.835,
                    "bgcolor": "white",
                    "margin": {"l": 50, "r": 20, "t": 20, "b": 40}
                },
                "font": {
                    "family": "Times New Roman",
                    "size": 8,
                    "color": "black"
                },
                "xaxis": {
                    "title": {
                        "font": {"size": 9, "family": "Times New Roman"},
                        "standoff": 5
                    },
                    "tickfont": {"size": 8, "family": "Times New Roman"},
                    "showgrid": True,
                    "gridcolor": "#E5E5E5",
                    "gridwidth": 0.5,
                    "linewidth": 0.75,
                    "linecolor": "black",
                    "ticks": "outside",
                    "ticklen": 3,
                    "tickwidth": 0.75,
                    "mirror": True
                },
                "yaxis": {
                    "title": {
                        "font": {"size": 9, "family": "Times New Roman"},
                        "standoff": 5
                    },
                    "tickfont": {"size": 8, "family": "Times New Roman"},
                    "showgrid": True,
                    "gridcolor": "#E5E5E5",
                    "gridwidth": 0.5,
                    "linewidth": 0.75,
                    "linecolor": "black",
                    "ticks": "outside",
                    "ticklen": 3,
                    "tickwidth": 0.75,
                    "mirror": True
                },
                "legend": {
                    "font": {"size": 7, "family": "Times New Roman"},
                    "borderwidth": 0
                }
            },

            "apl": {  # Applied Physics Letters
                "figure": {
                    "width": 85 * 2.835,
                    "height": 85 * 2.835,
                    "bgcolor": "white",
                    "margin": {"l": 50, "r": 20, "t": 20, "b": 40}
                },
                "font": {
                    "family": "Times New Roman",
                    "size": 8,
                    "color": "black"
                },
                "xaxis": {
                    "title": {
                        "font": {"size": 9, "family": "Times New Roman"},
                        "standoff": 5
                    },
                    "tickfont": {"size": 8, "family": "Times New Roman"},
                    "showgrid": True,
                    "gridcolor": "#E5E5E5",
                    "gridwidth": 0.5,
                    "linewidth": 0.75,
                    "linecolor": "black",
                    "ticks": "outside",
                    "ticklen": 3,
                    "tickwidth": 0.75,
                    "mirror": True
                },
                "yaxis": {
                    "title": {
                        "font": {"size": 9, "family": "Times New Roman"},
                        "standoff": 5
                    },
                    "tickfont": {"size": 8, "family": "Times New Roman"},
                    "showgrid": True,
                    "gridcolor": "#E5E5E5",
                    "gridwidth": 0.5,
                    "linewidth": 0.75,
                    "linecolor": "black",
                    "ticks": "outside",
                    "ticklen": 3,
                    "tickwidth": 0.75,
                    "mirror": True
                },
                "legend": {
                    "font": {"size": 7, "family": "Times New Roman"},
                    "borderwidth": 0
                }
            },

            "nano_letters": {
                "figure": {
                    "width": 88 * 2.835,
                    "height": 88 * 2.835,
                    "bgcolor": "white",
                    "margin": {"l": 50, "r": 20, "t": 20, "b": 40}
                },
                "font": {
                    "family": "Arial",
                    "size": 8,
                    "color": "black"
                },
                "xaxis": {
                    "title": {
                        "font": {"size": 9, "family": "Arial"},
                        "standoff": 5
                    },
                    "tickfont": {"size": 8, "family": "Arial"},
                    "showgrid": True,
                    "gridcolor": "#E5E5E5",
                    "gridwidth": 0.5,
                    "linewidth": 0.75,
                    "linecolor": "black",
                    "ticks": "outside",
                    "ticklen": 3,
                    "tickwidth": 0.75,
                    "mirror": True
                },
                "yaxis": {
                    "title": {
                        "font": {"size": 9, "family": "Arial"},
                        "standoff": 5
                    },
                    "tickfont": {"size": 8, "family": "Arial"},
                    "showgrid": True,
                    "gridcolor": "#E5E5E5",
                    "gridwidth": 0.5,
                    "linewidth": 0.75,
                    "linecolor": "black",
                    "ticks": "outside",
                    "ticklen": 3,
                    "tickwidth": 0.75,
                    "mirror": True
                },
                "legend": {
                    "font": {"size": 7, "family": "Arial"},
                    "borderwidth": 0
                }
            }
        }

    @staticmethod
    def apply_template(fig, template_name: str):
        """Applique un template à une figure existante"""
        templates = ScientificTemplates.get_templates()
        if template_name not in templates:
            raise ValueError(f"Template '{template_name}' non trouvé")

        template = templates[template_name]
        fig.update_layout(
            width=template["figure"]["width"],
            height=template["figure"]["height"],
            plot_bgcolor=template["figure"]["bgcolor"],
            paper_bgcolor=template["figure"]["bgcolor"],
            margin=template["figure"]["margin"],
            font=template["font"],
            xaxis=template["xaxis"],
            yaxis=template["yaxis"],
            legend=template["legend"]
        )
        return fig


def get_web_template():
    return {
        "figure": {
            "width": 1200,  # Large vue pour écrans modernes
            "height": 600,  # Ratio 2:1 pour une bonne visualisation
            "bgcolor": "#FFFFFF",
            "margin": {
                "l": 80,
                "r": 40,
                "t": 40,
                "b": 60,
                "pad": 10
            }
        },
        "font": {
            "family": "Roboto, Arial, sans-serif",
            "size": 14,
            "color": "#2F3337"
        },
        "xaxis": {
            "title": {
                "font": {
                    "family": "Roboto, Arial, sans-serif",
                    "size": 16,
                    "color": "#2F3337"
                },
                "standoff": 15
            },
            "tickfont": {
                "family": "Roboto, Arial, sans-serif",
                "size": 12
            },
            "showgrid": True,
            "gridcolor": "#E1E5EA",
            "gridwidth": 1,
            "linewidth": 1,
            "linecolor": "#2F3337",
            "ticks": "outside",
            "ticklen": 5,
            "tickwidth": 1,
            "mirror": True,
            "showline": True,
            # Paramètres interactifs
            "showspikes": True,
            "spikecolor": "#2F3337",
            "spikethickness": 1,
            "spikedash": "dot",
            "spikesnap": "cursor",
            # Amélioration de la lisibilité
            "showticklabels": True,
            "tickangle": 0,
            "tickprefix": "",
            "ticksuffix": "",
            "separatethousands": True
        },
        "yaxis": {
            "title": {
                "font": {
                    "family": "Roboto, Arial, sans-serif",
                    "size": 16,
                    "color": "#2F3337"
                },
                "standoff": 15
            },
            "tickfont": {
                "family": "Roboto, Arial, sans-serif",
                "size": 12
            },
            "showgrid": True,
            "gridcolor": "#E1E5EA",
            "gridwidth": 1,
            "linewidth": 1,
            "linecolor": "#2F3337",
            "ticks": "outside",
            "ticklen": 5,
            "tickwidth": 1,
            "mirror": True,
            "showline": True,
            # Paramètres interactifs
            "showspikes": True,
            "spikecolor": "#2F3337",
            "spikethickness": 1,
            "spikedash": "dot",
            "spikesnap": "cursor",
            # Amélioration de la lisibilité
            "showticklabels": True,
            "tickangle": 0,
            "tickprefix": "",
            "ticksuffix": "",
            "separatethousands": True
        },
        "legend": {
            "font": {
                "family": "Roboto, Arial, sans-serif",
                "size": 12,
                "color": "#2F3337"
            },
            "bgcolor": "rgba(255, 255, 255, 0.8)",
            "bordercolor": "#E1E5EA",
            "borderwidth": 1,
            "orientation": "h",  # Légende horizontale
            "yanchor": "bottom",
            "y": 1.02,  # Au-dessus du graphique
            "xanchor": "center",
            "x": 0.5
        },
        # Paramètres supplémentaires pour le web
        "modebar": {
            "bgcolor": "rgba(255, 255, 255, 0.8)",
            "color": "#2F3337",
            "activecolor": "#1f77b4"
        },
        "hoverlabel": {
            "font": {
                "family": "Roboto, Arial, sans-serif",
                "size": 12
            },
            "bgcolor": "rgba(255, 255, 255, 0.95)",
            "bordercolor": "#2F3337",
            "namelength": -1  # Pas de troncature
        },
        # Configuration des interactions
        "config": {
            "displayModeBar": True,
            "displaylogo": False,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            "modeBarButtonsToAdd": ["drawopenpath", "eraseshape"],
            "toImageButtonOptions": {
                "format": "svg",
                "filename": "custom_figure",
                "height": 600,
                "width": 1200,
                "scale": 1
            },
            "responsive": True
        }
    }