import re
from typing import Dict

import matplotlib.pyplot as plt
import lmfit
import numpy as np
import plotly.graph_objects as go
from numba import jit

from fit_builder.template_journaux import ScientificTemplates, get_web_template
import sympy
from sympy.parsing.sympy_parser import parse_expr


class FitBuilder:
    def __init__(self):
        self.expression = ""
        self.fit_manager = None
        self.custom_models = {}

    def create_base_expression(self, components: list) -> str:
        """
        Crée l'expression de base avec les composants demandés
        components: liste de tuples (type, nombre)
        Ex: [('lorentzian', 3), ('gaussian', 2)]
        """
        valid_types = {'lorentzian', 'gaussian', 'voigt', 'constant', 'linear'}
        for model_type, count in components:
            if model_type not in valid_types:
                raise ValueError(f"Type de modèle invalide: {model_type}")
            if not isinstance(count, int) or count <= 0:
                raise ValueError(f"Nombre invalide pour {model_type}: {count}")

        parts = []
        for model_type, count in components:
            prefix = 'L' if model_type == 'lorentzian' else 'G' if model_type == 'gaussian' else 'V'
            for i in range(count):
                parts.append(f"{prefix}{i + 1}:{model_type}()")

        self.expression = " + ".join(parts)
        return self.expression

    def set_parameter_constraint(self, component_id: str, param: str,
                                 constraint_type: str, value: float) -> str:
        """
        Modifie ou ajoute une contrainte sur un paramètre
        Ex: set_parameter_constraint('L1', 'center', 'fixed', 5.0)
        """
        # Parse l'expression existante
        components = self.expression.split('+')
        new_components = []

        for comp in components:
            comp = comp.strip()
            if comp.startswith(component_id):
                name, rest = comp.split(':')
                model_type = rest[:rest.find('(')] if '(' in rest else rest

                # Construit la nouvelle contrainte
                constraint = {
                    'fixed': f"{param}={value}",
                    'min': f"{param}>{value}",
                    'max': f"{param}<{value}",
                    'initial': f"{param}~{value}"
                }[constraint_type]

                # Ajoute ou remplace la contrainte
                if '(' not in comp:
                    new_comp = f"{name}:{model_type}({constraint})"
                else:
                    params = comp[comp.find('(') + 1:comp.find(')')]
                    param_list = [p.strip() for p in params.split(',') if p.strip()]
                    param_list = [p for p in param_list if not p.startswith(param)]
                    param_list.append(constraint)
                    new_comp = f"{name}:{model_type}({','.join(param_list)})"

                new_components.append(new_comp)
            else:
                new_components.append(comp)

        self.expression = " + ".join(new_components)
        return self.expression

    def link_parameters(self, param1: str, param2: str, relation: str) -> str:
        """
        Lie deux paramètres avec une relation
        Ex: link_parameters('L1_center', 'L2_center', 'same')
        """
        # À implémenter selon les besoins
        pass

    def add_component(self, model_type: str, position: str = "end") -> str:
        """
        Ajoute un nouveau composant à l'expression
        """
        # Détermine le prochain ID disponible
        prefix = 'L' if model_type == 'lorentzian' else 'G' if model_type == 'gaussian' else 'V'
        existing = [c.split(':')[0] for c in self.expression.split('+')]
        same_type = [e for e in existing if e.startswith(prefix)]
        new_id = f"{prefix}{len(same_type) + 1}"

        new_component = f"{new_id}:{model_type}()"

        if not self.expression:
            self.expression = new_component
        else:
            self.expression = f"{self.expression} + {new_component}"

        return self.expression

    def build_fit(self):
        """
        Crée le fit manager à partir de l'expression actuelle
        """
        if not hasattr(self, 'fit_manager') or self.fit_manager is None:
            self.fit_manager = AdvancedFitManager()

        self.fit_manager.setup_from_expression(self.expression)
        return self.fit_manager

    def parse_custom_expression(self, expression: str) -> str:
        """
        Parse une expression personnalisée comme 'P1:ax^3 + bx^2 + cx + d(a=2, b, c~3, d)'
        """
        components = []
        for comp in expression.split('+'):
            comp = comp.strip()
            if ':' in comp:
                name, expr = comp.split(':')
                if '(' in expr:
                    # Expression avec paramètres
                    math_expr, params = expr.split('(')
                    params = params.rstrip(')')
                    # Normalise l'expression
                    math_expr = self._normalize_expression(math_expr)
                    # Crée le modèle personnalisé
                    model = CustomModel(math_expr, name=name)
                    self.custom_models[name] = model
                    # Parse les paramètres
                    param_specs = self._parse_parameters(params)
                    components.append(f"{name}:custom({param_specs})")
                else:
                    # Expression sans paramètres
                    math_expr = self._normalize_expression(expr)
                    model = CustomModel(math_expr, name=name)
                    self.custom_models[name] = model
                    components.append(f"{name}:custom()")
            else:
                components.append(comp)

        return " + ".join(components)

    def _normalize_expression(self, expr: str) -> str:
        """
        Normalise une expression mathématique
        Ex: 'ax^2' -> 'a*x**2'
        """
        # Remplace ^ par **
        expr = expr.replace('^', '**')

        # Ajoute les * manquants
        expr = re.sub(r'([a-zA-Z0-9])([a-zA-Z])', r'\1*\2', expr)

        return expr

    def _parse_parameters(self, params_str: str) -> str:
        """
        Parse les spécifications des paramètres
        Ex: 'a=2, b, c~3, d' -> 'a=2, b~1, c~3, d~1'
        """
        param_specs = []
        for param in params_str.split(','):
            param = param.strip()
            if '=' in param:
                # Valeur fixe
                name, value = param.split('=')
                param_specs.append(f"{name.strip()}={value.strip()}")
            elif '~' in param:
                # Valeur initiale
                name, value = param.split('~')
                param_specs.append(f"{name.strip()}~{value.strip()}")
            else:
                # Paramètre libre avec valeur par défaut
                param_specs.append(f"{param.strip()}~1")

        return ', '.join(param_specs)


class CustomModel(lmfit.Model):
    def __init__(self, expression_str, name=None, **kwargs):
        # Parse l'expression avec sympy
        self.expr = parse_expr(expression_str.replace('^', '**'))
        # Trouve toutes les variables sauf 'x'
        self.vars = sorted([str(s) for s in self.expr.free_symbols if str(s) != 'x'])
        self.x_symbol = sympy.Symbol('x')

        # Crée la fonction d'évaluation avec les paramètres préfixés
        def eval_func(x, **params):
            # Retire le préfixe pour l'évaluation
            prefix = name if name else ''
            param_dict = {var: params[f'{prefix}{var}'] for var in self.vars}
            param_dict['x'] = x
            return sympy.lambdify(['x'] + self.vars, self.expr)(*([x] + [param_dict[var] for var in self.vars]))

        # Initialise le modèle lmfit
        super().__init__(eval_func, name=name, independent_vars=['x'], **kwargs)

        # Définit les paramètres par défaut avec le préfixe
        for var in self.vars:
            # Utilise le même format que les modèles standards (sans underscore)
            self.set_param_hint(f'{name}{var}', value=1.0)


class AdvancedFitManager:
    def __init__(self):
        self.models = {}
        self.composite_model = None
        self.params = None
        self.result = None
        self.x_data = None
        self.y_data = None
        self.expression = ""
        self.plot_style = PlotStyleBuilder()
        self.custom_models = {}  # Pour stocker les modèles personnalisés
        self.pending_expressions = []  # Pour stocker les expressions à appliquer

    def _is_standard_model(self, model_type: str) -> bool:
        """Vérifie si c'est un modèle standard"""
        standard_models = {
            'gaussian', 'lorentzian', 'voigt', 'constant', 'linear',
            'exponential', 'polynomial'
        }
        return model_type.lower() in standard_models

    def set_data(self, x_data: np.ndarray, y_data: np.ndarray):
        """Définit les données à fitter"""
        self.x_data = np.array(x_data)
        self.y_data = np.array(y_data)
        return "Données chargées avec succès"

    def _get_model_class(self, model_type: str) -> lmfit.Model:
        """Retourne la classe de modèle appropriée"""
        model_map = {
            'gaussian': lmfit.models.GaussianModel,
            'lorentzian': lmfit.models.LorentzianModel,
            'voigt': lmfit.models.VoigtModel,
            'constant': lmfit.models.ConstantModel,
            'linear': lmfit.models.LinearModel,
            'exponential': lmfit.models.ExponentialModel,
            'polynomial': lmfit.models.PolynomialModel
        }
        if model_type.lower() not in model_map:
            raise ValueError(f"Type de modèle non supporté: {model_type}")
        return model_map[model_type.lower()]

    def set_parameter_expression(self, param_name: str, expression: str):
        """
        Définit une expression pour un paramètre en fonction d'autres paramètres

        Parameters:
        -----------
        param_name : str
            Nom du paramètre à contraindre (ex: 'P1a' ou 'L1center')
        expression : str
            Expression mathématique (ex: '2 * P1b' ou 'L1center + 10')
        """
        if self.params is None:
            raise ValueError("Les paramètres n'ont pas encore été initialisés")

        # Vérifie si le paramètre existe
        if param_name not in self.params and param_name.replace('_', '') not in self.params:
            raise ValueError(f"Paramètre {param_name} non trouvé")

        # Utilise le bon format de nom
        actual_param_name = param_name if param_name in self.params else param_name.replace('_', '')

        try:
            # Définit l'expression pour le paramètre
            self.params[actual_param_name].expr = expression
            return f"Expression {expression} définie pour {actual_param_name}"
        except Exception as e:
            raise ValueError(f"Erreur lors de la définition de l'expression: {str(e)}")

    def setup_from_expression(self, expression: str):
        """Configure le fit à partir d'une expression"""
        if not expression or not expression.strip():
            raise ValueError("Expression vide")

        self.expression = expression
        self.models.clear()
        self.custom_models.clear()
        self.composite_model = None
        self.params = None
        self.pending_expressions = []

        # Séparation intelligente des composants
        components = []
        current = ""
        in_parentheses = 0

        i = 0
        while i < len(expression):
            char = expression[i]

            # Gestion des parenthèses
            if char == '(':
                in_parentheses += 1
            elif char == ')':
                in_parentheses -= 1

            # Gestion des séparateurs de modèles (+ ou -)
            if char in ['+', '-'] and in_parentheses == 0:
                # Vérifie si c'est vraiment un séparateur de modèle
                prev_char = expression[i - 1] if i > 0 else ''
                next_char = expression[i + 1] if i + 1 < len(expression) else ''

                # C'est un séparateur si le prochain caractère non-espace est une lettre
                # suivie d'un chiffre et d'un deux-points
                is_separator = False
                if prev_char == ')':
                    is_separator = True
                else:
                    # Regarde en avant pour trouver un pattern comme "L1:" ou "G1:"
                    j = i + 1
                    while j < len(expression) and expression[j].isspace():
                        j += 1
                    if j < len(expression):
                        look_ahead = expression[j:j + 4]  # Prend quelques caractères
                        if any(look_ahead.startswith(prefix) for prefix in ['L', 'G', 'P', 'V', 'C']):
                            # Vérifie si c'est suivi d'un chiffre et d'un deux-points
                            for k in range(j + 1, min(j + 4, len(expression))):
                                if expression[k] == ':':
                                    is_separator = True
                                    break

                if is_separator:
                    if current.strip():
                        components.append(current.strip())
                    current = ""
                    i += 1
                    continue

            current += char
            i += 1

        if current.strip():
            components.append(current.strip())

        # Traitement des composants
        for component in components:
            if ':' not in component:
                continue

            name, spec = component.split(':', 1)
            name = name.strip()
            spec = spec.strip()

            # Vérifie que le nom commence par une lettre
            if not name[0].isalpha():
                raise ValueError(f"Le nom du modèle doit commencer par une lettre: {name}")

            # Extraction des paramètres et des relations
            params_str = ""
            relations = []

            if '(' in spec:
                model_type = spec[:spec.find('(')].strip()
                params_part = spec[spec.find('(') + 1:spec.rfind(')')].strip()

                # Sépare les paramètres des relations
                if '|' in params_part:
                    params_str, relations_str = params_part.split('|', 1)
                    relations = [rel.strip() for rel in relations_str.split(',') if rel.strip()]
                else:
                    params_str = params_part
            else:
                model_type = spec
                params_str = ""

            # Création du modèle approprié
            if self._is_standard_model(model_type):
                model_class = self._get_model_class(model_type)
                self.models[name] = model_class(prefix=name)
            else:
                # Pour un modèle personnalisé, l'expression complète avant les paramètres
                math_expr = spec[:spec.find('(')] if '(' in spec else spec
                math_expr = self._normalize_expression(math_expr)
                custom_model = CustomModel(math_expr, name=name)
                self.models[name] = custom_model
                self.custom_models[name] = custom_model

            # Stocke les relations
            for relation in relations:
                if '=' in relation:
                    param, expr = relation.split('=', 1)
                    param = param.strip()
                    expr = expr.strip()
                    if not param.startswith(name):
                        param = f"{name}{param}"
                    self.pending_expressions.append((param, expr))

        # Construction du modèle composite
        self._build_composite_model()

        # Configuration des paramètres
        for component in components:
            if ':' not in component:
                continue

            name, spec = component.split(':', 1)
            name = name.strip()

            if '(' in spec:
                params_part = spec[spec.find('(') + 1:spec.rfind(')')].strip()
                if '|' in params_part:
                    params_str = params_part.split('|', 1)[0].strip()
                else:
                    params_str = params_part

                if params_str:
                    self._setup_parameters(name, params_str)

        # Traitement des relations avec préfixes automatiques
        processed_relations = []
        for param, expr in self.pending_expressions:
            try:
                # Assure que le paramètre de gauche a un préfixe
                if not any(param.startswith(prefix) for prefix in ['L', 'G', 'P', 'V', 'C']):
                    # Trouve le préfixe approprié basé sur le contexte
                    for name in self.models.keys():
                        if any(param.replace(name, '') == p.replace(name, '')
                               for p in self.params.keys() if p.startswith(name)):
                            param = f"{name}{param}"
                            break

                # Traite l'expression de droite
                expr_parts = re.findall(r'[a-zA-Z][a-zA-Z0-9_]*', expr)
                for part in expr_parts:
                    if not any(part.startswith(prefix) for prefix in ['L', 'G', 'P', 'V', 'C']):
                        # Trouve le préfixe approprié
                        for name in self.models.keys():
                            if any(part == p.replace(name, '')
                                   for p in self.params.keys() if p.startswith(name)):
                                expr = re.sub(r'\b' + part + r'\b', f"{name}{part}", expr)
                                break

                processed_relations.append((param, expr))
            except Exception as e:
                print(f"Erreur lors du traitement de la relation {param}={expr}: {str(e)}")

        # Application des relations traitées
        for param, expr in processed_relations:
            try:
                if param in self.params:
                    self.params[param].expr = expr
                elif param.replace('_', '') in self.params:
                    self.params[param.replace('_', '')].expr = expr
            except Exception as e:
                print(f"Erreur lors de l'application de la relation {param}={expr}: {str(e)}")

        return "Configuration effectuée avec succès"

    def _normalize_expression(self, expr: str) -> str:
        """Normalise une expression mathématique"""
        # Remplace ^ par **
        expr = expr.replace('^', '**')

        # Ajoute les * manquants
        expr = re.sub(r'([a-zA-Z0-9])([a-zA-Z])', r'\1*\2', expr)
        expr = re.sub(r'([a-zA-Z0-9])([a-zA-Z])', r'\1*\2', expr)  # Double passe pour ax^2 -> a*x**2

        return expr

    def _build_composite_model(self):
        """Construit le modèle composite"""
        if not self.models:
            raise ValueError("Aucun modèle défini")

        # Debug: afficher les modèles
        print("Modèles disponibles:", self.models.keys())

        models_list = list(self.models.values())
        self.composite_model = models_list[0]
        for model in models_list[1:]:
            self.composite_model += model

        # Crée les paramètres initiaux
        self.params = self.composite_model.make_params()

        # Applique les expressions en attente
        for param_name, expression in self.pending_expressions:
            self.set_parameter_expression(param_name, expression)

        # Debug: afficher les paramètres disponibles
        print("Paramètres disponibles:", list(self.params.keys()))

        return "Modèle composite construit avec succès"

    def _get_param_name_mapping(self, model_type: str) -> dict:
        """Retourne le mapping des noms de paramètres pour chaque type de modèle"""
        mappings = {
            'gaussian': {
                'center': 'center',
                'amplitude': 'amplitude',
                'sigma': 'sigma',
                'fwhm': 'fwhm',
                'height': 'height'
            },
            'lorentzian': {
                'center': 'center',
                'amplitude': 'amplitude',
                'sigma': 'sigma',
                'fwhm': 'fwhm',
                'height': 'height'
            },
            'voigt': {
                'center': 'center',
                'amplitude': 'amplitude',
                'sigma': 'sigma',
                'gamma': 'gamma'
            },
            'constant': {
                'c': 'c'
            },
            'linear': {
                'slope': 'slope',
                'intercept': 'intercept'
            }
        }
        return mappings.get(model_type.lower(), {})

    def _setup_parameters(self, model_name: str, params_str: str):
        """Configure les paramètres d'un modèle"""
        if not params_str:
            return

        for param_spec in params_str.split(','):
            param_spec = param_spec.strip()
            if not param_spec:
                continue

            try:
                if '=' in param_spec:  # valeur fixe
                    param_name, value = param_spec.split('=')
                    param_name = param_name.strip()
                    # Essaie les deux formats de nom
                    full_param_name = f"{model_name}_{param_name}"
                    alt_param_name = f"{model_name}{param_name}"
                    if alt_param_name in self.params:
                        self.params[alt_param_name].set(value=float(value), vary=False)
                    else:
                        print(f"Paramètre {alt_param_name} non trouvé")

                elif '~' in param_spec:  # valeur initiale
                    param_name, value = param_spec.split('~')
                    param_name = param_name.strip()
                    # Essaie les deux formats de nom
                    full_param_name = f"{model_name}_{param_name}"
                    alt_param_name = f"{model_name}{param_name}"
                    if alt_param_name in self.params:
                        self.params[alt_param_name].set(value=float(value))
                    else:
                        print(f"Paramètre {alt_param_name} non trouvé")

                elif '>' in param_spec:  # borne inférieure
                    param_name, value = param_spec.split('>')
                    param_name = param_name.strip()
                    # Essaie les deux formats de nom
                    full_param_name = f"{model_name}_{param_name}"
                    alt_param_name = f"{model_name}{param_name}"
                    if alt_param_name in self.params:
                        self.params[alt_param_name].set(min=float(value))
                    else:
                        print(f"Paramètre {alt_param_name} non trouvé")

                elif '<' in param_spec:  # borne supérieure
                    param_name, value = param_spec.split('<')
                    param_name = param_name.strip()
                    # Essaie les deux formats de nom
                    full_param_name = f"{model_name}_{param_name}"
                    alt_param_name = f"{model_name}{param_name}"
                    if alt_param_name in self.params:
                        self.params[alt_param_name].set(max=float(value))
                    else:
                        print(f"Paramètre {alt_param_name} non trouvé")

                else:
                    # Paramètre libre avec valeur par défaut
                    param_name = param_spec.strip()
                    # Essaie les deux formats de nom
                    full_param_name = f"{model_name}_{param_name}"
                    alt_param_name = f"{model_name}{param_name}"
                    if alt_param_name in self.params:
                        self.params[alt_param_name].set(value=1.0)
                    else:
                        print(f"Paramètre {alt_param_name} non trouvé")

            except Exception as e:
                print(f"Erreur lors de la configuration du paramètre {param_spec} pour {model_name}: {str(e)}")

    def modify_parameter(self, param_name: str, **kwargs):
        """Modifie un paramètre existant"""
        if self.params is None:
            raise ValueError("Aucun paramètre défini")

        if param_name not in self.params:
            raise ValueError(f"Paramètre {param_name} non trouvé")

        self.params[param_name].set(**kwargs)
        return f"Paramètre {param_name} modifié avec succès"

    def link_parameters(self, param1: str, param2: str, relation: str = 'same', offset: float = 0):
        """Lie deux paramètres entre eux"""
        if self.params is None:
            raise ValueError("Aucun paramètre défini")

        if param1 not in self.params or param2 not in self.params:
            raise ValueError("Paramètres non trouvés")

        if relation == 'same':
            self.params[param2].expr = f"{param1}"
        elif relation == 'offset':
            self.params[param2].expr = f"{param1} + {offset}"
        else:
            raise ValueError(f"Relation non supportée: {relation}")

        return f"Paramètres {param1} et {param2} liés avec succès"

    def fit(self, method: str = 'leastsq', **kwargs):
        """Effectue le fit"""
        if self.composite_model is None:
            raise ValueError("Aucun modèle défini")
        if self.x_data is None or self.y_data is None:
            raise ValueError("Données non définies")

        self.result = self.composite_model.fit(
            self.y_data,
            self.params,
            x=self.x_data,
            method=method,
            **kwargs
        )
        return "Fit effectué avec succès"

    def web_plot_result(self, show_components: bool = False, template: str = "web"):
        if self.result is None:
            raise ValueError("Aucun résultat à afficher")

        fig = go.Figure()

        # Style des données
        data_style = dict(
            marker=dict(
                size=8,
                opacity=0.7,
                line=dict(width=1, color="white")
            ),
            error_y=dict(
                type='data',
                thickness=1,
                width=3
            )
        )

        # Ajouter les données
        fig.add_trace(
            go.Scatter(
                x=self.x_data,
                y=self.y_data,
                mode='markers',
                name='Données',
                marker=dict(
                    color='#1f77b4',
                    **data_style['marker']
                ),
                hovertemplate='x: %{x:.3f}<br>y: %{y:.3f}<extra></extra>'
            )
        )

        # Ajouter le fit
        fig.add_trace(
            go.Scatter(
                x=self.x_data,
                y=self.result.best_fit,
                mode='lines',
                name='Fit total',
                line=dict(
                    color='#ff7f0e',
                    width=2,
                    dash='solid'
                ),
                hovertemplate='x: %{x:.3f}<br>y: %{y:.3f}<extra></extra>'
            )
        )

        # Ajouter les composants si demandé
        if show_components:
            comps = self.result.eval_components(x=self.x_data)
            colors = ['#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2']
            for i, (name, comp) in enumerate(comps.items()):
                fig.add_trace(
                    go.Scatter(
                        x=self.x_data,
                        y=comp,
                        mode='lines',
                        name=name,
                        line=dict(
                            color=colors[i % len(colors)],
                            width=1.5,
                            dash='dash'
                        ),
                        hovertemplate='x: %{x:.3f}<br>y: %{y:.3f}<extra></extra>'
                    )
                )

        # Appliquer le template web
        web_template = get_web_template()
        fig.update_layout(
            template="plotly_white",
            width=web_template["figure"]["width"],
            height=web_template["figure"]["height"],
            plot_bgcolor=web_template["figure"]["bgcolor"],
            paper_bgcolor=web_template["figure"]["bgcolor"],
            margin=web_template["figure"]["margin"],
            font=web_template["font"],
            xaxis=web_template["xaxis"],
            yaxis=web_template["yaxis"],
            legend=web_template["legend"],
            hoverlabel=web_template["hoverlabel"],
            # Titre du graphique
            title=dict(
                text="Résultats du fit",
                font=dict(size=20, family="Roboto, Arial, sans-serif"),
                x=0.5,
                y=0.95
            ),
            # Ajout d'une barre de zoom
            updatemenus=[dict(
                type="buttons",
                showactive=False,
                buttons=[
                    dict(
                        label="Reset Zoom",
                        method="relayout",
                        args=[{"xaxis.range": None, "yaxis.range": None}]
                    )
                ],
                pad={"r": 10, "t": 10},
                x=0.05,
                y=1.1,
            )]
        )

        # Configuration supplémentaire
        fig.update_layout(hovermode='closest')

        return fig

    def plot_result(self, show_components: bool = False, template: str = None, add_controls: bool = False):
        """
        Crée un graphique avec un style personnalisé

        Parameters:
        -----------
        style_expression : str
            Expression définissant le style du graphique
            Ex: 'template:nature;xaxis:log10,label="Energy (eV)"'
        """

        if self.result is None:
            raise ValueError("Aucun résultat à afficher")

        # Créer la figure
        fig = go.Figure()

        # Ajouter les données
        fig.add_trace(
            go.Scatter(
                x=self.x_data,
                y=self.y_data,
                mode='markers',
                name='Données',
                marker=dict(color='blue', size=8, opacity=0.5)
            )
        )

        # Ajouter le fit total
        fig.add_trace(
            go.Scatter(
                x=self.x_data,
                y=self.result.best_fit,
                mode='lines',
                name='Fit total',
                line=dict(color='red', width=2)
            )
        )

        # Ajouter les composants individuels si demandé
        if show_components:
            comps = self.result.eval_components(x=self.x_data)
            colors = ['green', 'purple', 'orange', 'brown', 'pink']  # Couleurs pour les composants
            for i, (name, comp) in enumerate(comps.items()):
                fig.add_trace(
                    go.Scatter(
                        x=self.x_data,
                        y=comp,
                        mode='lines',
                        name=name,
                        line=dict(
                            color=colors[i % len(colors)],
                            width=1,
                            dash='dash'
                        )
                    )
                )

        """
                if style_expression:
                    style_dict = self.plot_style.parse_expression(style_expression)
                    layout_updates = self._apply_plot_style(style_dict)
                    fig.update_layout(**layout_updates)
                """



        # Appliquer le style si spécifié
        if template:
            fig = ScientificTemplates.apply_template(fig, template)
            # Mise en page de base (sans les boutons)
            fig.update_layout(
                showlegend=True,
                legend=dict(
                    yanchor="top",
                    y=0.99,
                    xanchor="left",
                    x=0.01
                )
            )
        else:
            # Mise en page
            fig.update_layout(
                title='Résultats du fit',
                xaxis_title='X',
                yaxis_title='Y',
                hovermode='closest',
                template='plotly_white',
                showlegend=True,
                legend=dict(
                    yanchor="top",
                    y=0.99,
                    xanchor="left",
                    x=0.01
                )
            )

        # Configuration de la légende interactive
        fig.update_layout(
            showlegend=True,
            legend=dict(
                # Position initiale
                yanchor="top",
                y=0.99,
                xanchor="right",
                x=0.99,
                # Style
                bgcolor="rgba(255, 255, 255, 0.8)",
                bordercolor="rgba(0, 0, 0, 0.3)",
                borderwidth=1,
            ),
            # Configuration globale
            dragmode='pan',  # Mode de drag par défaut
            clickmode='event+select',  # Permet la sélection
            hovermode='closest'
        )

        # Configuration pour l'export
        fig.update_layout(
            # Permet de sauvegarder en haute qualité
            images=[dict(
                source="",
                xref="paper",
                yref="paper",
                x=0,
                y=0,
                sizex=1,
                sizey=1,
                sizing="stretch",
                layer="below"
            )]
        )

        # Configuration pour le mode d'interaction
        fig.update_layout(
            modebar=dict(
                add=['drawopenpath', 'eraseshape', 'zoom', 'pan'],
                remove=['select', 'lasso2d']  # Retire les outils par défaut non désirés
            )
        )

        # Ajoute des boutons pour contrôler la légende si demandé
        if add_controls:
            fig.update_layout(
                updatemenus=[
                    dict(
                        type="buttons",
                        direction="left",
                        buttons=list([
                            dict(
                                args=[{"showlegend": True}],
                                label="Afficher légende",
                                method="relayout"
                            ),
                            dict(
                                args=[{"showlegend": False}],
                                label="Masquer légende",
                                method="relayout"
                            ),
                            dict(
                                args=[{"legend.font.size": 8}],
                                label="Petite légende",
                                method="relayout"
                            ),
                            dict(
                                args=[{"legend.font.size": 12}],
                                label="Grande légende",
                                method="relayout"
                            )
                        ]),
                        pad={"r": 10, "t": 10},
                        showactive=True,
                        x=0.11,
                        xanchor="left",
                        y=0.1,
                        yanchor="top"
                    )
                ]
            )

        # Configuration du titre centré
        fig.update_layout(
            title=dict(
                text='Résultats du fit',
                x=0.5,
                y=1.0,
                xanchor='center',
                yanchor='top',
                font=dict(size=22)
            )
        )

        config = {
            'editable': True,
            'displayModeBar': True,  # Affiche la barre d'outils
            'displaylogo': False,  # Cache le logo Plotly
            'modeBarButtonsToRemove': ['select', 'lasso2d'],
            'toImageButtonOptions': {
                'format': 'png',
                'filename': 'custom_image',
                'scale': 4  # Haute résolution
            },

        }

        return fig, config

    def _apply_plot_style(self, style_dict: dict):
        """Applique le style au graphique"""
        layout_updates = {}

        # Configuration des axes X
        if 'xaxis' in style_dict:
            xaxis_config = {}
            x_specs = style_dict['xaxis']

            # Type d'échelle
            if 'type' in x_specs:
                if x_specs['type'] == 'log10':
                    xaxis_config['type'] = 'log'
                else:
                    xaxis_config['type'] = x_specs['type']

            # Titre de l'axe
            if 'label' in x_specs:
                xaxis_config['title'] = {
                    'text': x_specs['label'],
                    'font': {
                        'family': x_specs.get('font', 'Arial'),
                        'size': self._parse_size(x_specs.get('size', '12pt'))
                    }
                }

            # Grille
            if 'grid' in x_specs:
                xaxis_config['showgrid'] = x_specs['grid'].get('visible', True)
                if 'color' in x_specs['grid']:
                    xaxis_config['gridcolor'] = x_specs['grid']['color']
                if 'width' in x_specs['grid']:
                    xaxis_config['gridwidth'] = x_specs['grid']['width']

            layout_updates['xaxis'] = xaxis_config

        # Configuration des axes Y (similaire à X)
        if 'yaxis' in style_dict:
            yaxis_config = {}
            y_specs = style_dict['yaxis']

            if 'type' in y_specs:
                if y_specs['type'] == 'log10':
                    yaxis_config['type'] = 'log'
                else:
                    yaxis_config['type'] = y_specs['type']

            if 'label' in y_specs:
                yaxis_config['title'] = {
                    'text': y_specs['label'],
                    'font': {
                        'family': y_specs.get('font', 'Arial'),
                        'size': self._parse_size(y_specs.get('size', '12pt'))
                    }
                }

            if 'grid' in y_specs:
                yaxis_config['showgrid'] = y_specs['grid'].get('visible', True)
                if 'color' in y_specs['grid']:
                    yaxis_config['gridcolor'] = y_specs['grid']['color']
                if 'width' in y_specs['grid']:
                    yaxis_config['gridwidth'] = y_specs['grid']['width']

            layout_updates['yaxis'] = yaxis_config

        # Configuration de la légende
        if 'legend' in style_dict:
            legend_config = {}
            legend_specs = style_dict['legend']

            if 'position' in legend_specs:
                pos = legend_specs['position'].split('-')
                legend_config.update({
                    'yanchor': pos[0],
                    'y': 0.99 if pos[0] == 'top' else 0.01,
                    'xanchor': pos[1],
                    'x': 0.99 if pos[1] == 'right' else 0.01
                })

            if 'frame' in legend_specs:
                legend_config['borderwidth'] = 1 if legend_specs['frame'] else 0

            layout_updates['showlegend'] = True
            layout_updates['legend'] = legend_config

        # Configuration de la figure
        if 'figure' in style_dict:
            figure_specs = style_dict['figure']
            if 'size' in figure_specs:
                layout_updates['width'] = figure_specs['size'][0]
                layout_updates['height'] = figure_specs['size'][1]
            if 'background' in figure_specs:
                layout_updates['plot_bgcolor'] = figure_specs['background']
                layout_updates['paper_bgcolor'] = figure_specs['background']

        return layout_updates

    def _parse_size(self, size_str: str) -> int:
        """Convertit une chaîne de taille (ex: '12pt') en nombre"""
        if isinstance(size_str, (int, float)):
            return int(size_str)
        size_str = size_str.strip()
        if size_str.endswith('pt'):
            return int(size_str[:-2])
        if size_str.endswith('px'):
            return int(size_str[:-2])
        return int(size_str)

    def plot_result_matplotlib(self, show_components: bool = False, ax=None):
        """
        Affiche les résultats

        Parameters:
        -----------
        show_components : bool
            Si True, affiche les composants individuels
        ax : matplotlib.axes.Axes, optional
            Axe sur lequel tracer. Si None, en crée un nouveau
        """
        if self.result is None:
            raise ValueError("Aucun résultat à afficher")

        # Créer une nouvelle figure si aucun axe n'est fourni
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))

        # Données
        ax.plot(self.x_data, self.y_data, 'bo', label='Données', alpha=0.5)

        # Fit total
        ax.plot(self.x_data, self.result.best_fit, 'r-', label='Fit total')

        # Composants individuels
        if show_components:
            comps = self.result.eval_components(x=self.x_data)
            for name, comp in comps.items():
                ax.plot(self.x_data, comp, '--', label=name)

        ax.legend()
        ax.grid(True)

        # Si on a créé une nouvelle figure, on l'affiche
        if ax is None:
            plt.show()

        return "Graphique affiché"

    def get_equation_string(self) -> str:
        """Retourne l'équation complète avec les coefficients ajustés"""
        if self.result is None:
            raise ValueError("Aucun résultat de fit disponible")

        equations = []

        for name, model in self.models.items():
            if isinstance(model, CustomModel):
                # Pour les modèles personnalisés
                expr = str(model.expr)  # Convertit en string
                # Remplace les variables par leurs valeurs
                for var in model.vars:
                    param_name = f"{name}{var}"
                    value = self.result.params[param_name].value
                    # Arrondit à 4 décimales
                    value_str = f"{value:.4f}".rstrip('0').rstrip('.')
                    # Remplace la variable par sa valeur (en tant que string)
                    expr = expr.replace(str(var), f"({value_str})")
                # Remplace les ** par ^
                expr = expr.replace('**', '^')
                equations.append(f"{name}: {expr}")
            else:
                # Pour les modèles standards
                if isinstance(model, lmfit.models.LorentzianModel):
                    amplitude = self.result.params[f"{name}amplitude"].value
                    center = self.result.params[f"{name}center"].value
                    sigma = self.result.params[f"{name}sigma"].value
                    amp_str = f"{amplitude:.4f}".rstrip('0').rstrip('.')
                    center_str = f"{center:.4f}".rstrip('0').rstrip('.')
                    sigma_str = f"{sigma:.4f}".rstrip('0').rstrip('.')
                    eq = f"{amp_str} / (1 + ((x - {center_str}) / {sigma_str})²)"
                    equations.append(f"{name}: {eq}")
                elif isinstance(model, lmfit.models.GaussianModel):
                    amplitude = self.result.params[f"{name}amplitude"].value
                    center = self.result.params[f"{name}center"].value
                    sigma = self.result.params[f"{name}sigma"].value
                    amp_str = f"{amplitude:.4f}".rstrip('0').rstrip('.')
                    center_str = f"{center:.4f}".rstrip('0').rstrip('.')
                    sigma_str = f"{sigma:.4f}".rstrip('0').rstrip('.')
                    eq = f"{amp_str} * exp(-(x - {center_str})² / (2 * {sigma_str}²))"
                    equations.append(f"{name}: {eq}")
                # Ajoutez d'autres modèles standards selon vos besoins

        # Combine toutes les équations
        full_equation = " + ".join(equations)
        return full_equation

    def get_fit_report(self, show_correl: bool = True) -> str:
        """Retourne le rapport de fit avec l'équation"""
        if self.result is None:
            return "Aucun résultat disponible"

        # Obtient le rapport standard
        report = self.result.fit_report(show_correl=show_correl)

        # Ajoute l'équation au début du rapport
        try:
            equation = self.get_equation_string()
            equation_section = "\n[[Equation complète]]\n" + equation + "\n\n"
            report = equation_section + report
        except Exception as e:
            print(f"Erreur lors de la génération de l'équation: {str(e)}")

        return report

    def get_parameter_value(self, param_name: str) -> Dict[str, float]:
        if self.result is None:
            raise ValueError("Aucun résultat disponible")

        if param_name not in self.result.params:
            raise ValueError(f"Paramètre {param_name} non trouvé")

        param = self.result.params[param_name]
        return {
            "value": param.value,
            "stderr": param.stderr if param.stderr is not None else float('nan'),
            "min": param.min if param.min is not None else float('-inf'),
            "max": param.max if param.max is not None else float('inf')
        }

    def get_fit_statistics(self) -> Dict[str, float]:
        """Retourne les statistiques du fit"""
        if self.result is None:
            raise ValueError("Aucun résultat disponible")

        return {
            "chi_square": self.result.chisqr,
            "reduced_chi_square": self.result.redchi,
            "aic": self.result.aic if hasattr(self.result, 'aic') else None,
            "bic": self.result.bic if hasattr(self.result, 'bic') else None
        }

    def save_result(self, filename: str):
        """Sauvegarde les résultats dans un fichier"""
        if self.result is None:
            raise ValueError("Aucun résultat à sauvegarder")

        with open(filename, 'w') as f:
            f.write("Expression de fit:\n")
            f.write(self.expression + "\n\n")
            f.write("Rapport de fit:\n")
            f.write(self.get_fit_report())

        return f"Résultats sauvegardés dans {filename}"

    def print_available_parameters(self):
        """Affiche tous les paramètres disponibles pour chaque modèle"""
        if self.params is None:
            print("Aucun paramètre disponible (modèle non initialisé)")
            return

        print("\nParamètres disponibles:")
        current_model = None
        for param_name in sorted(self.params.keys()):
            model = param_name.split('_')[0]
            if model != current_model:
                print(f"\n{model}:")
                current_model = model
            print(f"  - {param_name}")

    def customize_title(self, fig, text: str = None, font_family: str = None,
                        font_size: int = None, font_color: str = None,
                        x: float = None, y: float = None):
        """
        Personnalise le titre du graphique.

        Parameters:
        -----------
        fig : plotly.graph_objects.Figure
            Figure à modifier
        text : str, optional
            Texte du titre
        font_family : str, optional
            Police du titre (ex: 'Arial', 'Times New Roman')
        font_size : int, optional
            Taille de la police
        font_color : str, optional
            Couleur du titre (ex: 'black', '#000000', 'rgb(0,0,0)')
        x : float, optional
            Position horizontale (0 à 1)
        y : float, optional
            Position verticale (0 à 1)
        """
        title_update = {}

        if text is not None:
            title_update['text'] = text

        # Mise à jour de la police
        font_update = {}
        if font_family is not None:
            font_update['family'] = font_family
        if font_size is not None:
            font_update['size'] = font_size
        if font_color is not None:
            font_update['color'] = font_color
        if font_update:
            title_update['font'] = font_update

        # Mise à jour de la position
        if x is not None:
            title_update['x'] = x
        if y is not None:
            title_update['y'] = y

        # Application des modifications
        if title_update:
            fig.update_layout(title=title_update)

        return fig

    def customize_legend(self, fig, visible: bool = None, font_family: str = None,
                         font_size: int = None, font_color: str = None,
                         position: str = None):
        """
        Personnalise la légende du graphique.

        Parameters:
        -----------
        fig : plotly.graph_objects.Figure
            Figure à modifier
        visible : bool, optional
            Afficher/masquer la légende
        font_family : str, optional
            Police de la légende
        font_size : int, optional
            Taille de la police
        font_color : str, optional
            Couleur de la police
        position : str, optional
            Position de la légende ('top-left', 'top-right', 'bottom-left', 'bottom-right')
        """
        legend_update = {}

        if visible is not None:
            fig.update_layout(showlegend=visible)

        # Mise à jour de la police
        font_update = {}
        if font_family is not None:
            font_update['family'] = font_family
        if font_size is not None:
            font_update['size'] = font_size
        if font_color is not None:
            font_update['color'] = font_color
        if font_update:
            legend_update['font'] = font_update

        # Mise à jour de la position
        if position is not None:
            pos = position.split('-')
            legend_update.update({
                'yanchor': pos[0],
                'y': 0.99 if pos[0] == 'top' else 0.01,
                'xanchor': pos[1],
                'x': 0.99 if pos[1] == 'right' else 0.01
            })

        # Application des modifications
        if legend_update:
            fig.update_layout(legend=legend_update)

        return fig

    def customize_trace(self, fig, trace_index: int, line_color: str = None,
                        line_width: float = None, line_style: str = None,
                        marker_color: str = None, marker_size: float = None,
                        marker_symbol: str = None, opacity: float = None,
                        name: str = None):
        """
        Personnalise l'apparence d'une courbe spécifique.

        Parameters:
        -----------
        fig : plotly.graph_objects.Figure
            Figure à modifier
        trace_index : int
            Index de la courbe à modifier
        line_color : str, optional
            Couleur de la ligne
        line_width : float, optional
            Épaisseur de la ligne
        line_style : str, optional
            Style de la ligne ('solid', 'dot', 'dash', 'longdash', 'dashdot', 'longdashdot')
        marker_color : str, optional
            Couleur des marqueurs
        marker_size : float, optional
            Taille des marqueurs
        marker_symbol : str, optional
            Symbole des marqueurs ('circle', 'square', 'diamond', 'cross', etc.)
        opacity : float, optional
            Opacité de la courbe (0 à 1)
        name : str, optional
            Nom de la courbe dans la légende
        """
        if trace_index >= len(fig.data):
            raise ValueError(f"Index de trace invalide: {trace_index}")

        # Mise à jour de la ligne
        line_update = {}
        if line_color is not None:
            line_update['color'] = line_color
        if line_width is not None:
            line_update['width'] = line_width
        if line_style is not None:
            line_update['dash'] = line_style
        if line_update:
            fig.data[trace_index].line = line_update

        # Mise à jour des marqueurs
        marker_update = {}
        if marker_color is not None:
            marker_update['color'] = marker_color
        if marker_size is not None:
            marker_update['size'] = marker_size
        if marker_symbol is not None:
            marker_update['symbol'] = marker_symbol
        if marker_update:
            fig.data[trace_index].marker = marker_update

        # Autres mises à jour
        if opacity is not None:
            fig.data[trace_index].opacity = opacity
        if name is not None:
            fig.data[trace_index].name = name

        return fig

    def get_available_models(self) -> Dict[str, Dict]:
        """Retourne les informations sur tous les modèles disponibles"""
        models_info = {
            'help': {
                'title': 'Guide d\'utilisation des Expressions de Fit',
                'sections': [
                    {
                        'title': 'Types de modèles',
                        'type': 'list',
                        'items': [
                            {'code': 'gaussian',
                             'text': 'Fonction gaussienne - Modélise un pic avec une forme en cloche symétrique'},
                            {'code': 'lorentzian',
                             'text': 'Fonction lorentzienne - Pic avec des ailes plus larges'},
                            {'code': 'voigt',
                             'text': 'Convolution d\'une gaussienne et d\'une lorentzienne'},
                            {'code': 'constant',
                             'text': 'Ligne de base constante (y = c)'},
                            {'code': 'linear',
                             'text': 'Ligne de base linéaire (y = mx + b)'},
                            {'code': 'custom',
                             'text': 'Expression mathématique personnalisée (ex: ax^2 + bx + c)'}
                        ]
                    },
                    {
                        'title': 'Paramètres disponibles',
                        'type': 'model_params',
                        'items': {
                            'gaussian': 'center: Position du pic | amplitude: Amplitude | sigma: Largeur | fwhm: Largeur mi-hauteur | height: Hauteur',
                            'lorentzian': 'center: Position du pic | amplitude: Amplitude | sigma: Largeur | fwhm: Largeur mi-hauteur | height: Hauteur',
                            'voigt': 'center: Position du pic | amplitude: Amplitude | sigma: Largeur gaussienne | gamma: Largeur lorentzienne',
                            'constant': 'c: Valeur constante',
                            'linear': 'slope: Pente (m) | intercept: Ordonnée origine (b)',
                            'custom': 'Les paramètres sont les variables de votre expression (ex: pour ax^2 + bx + c, les paramètres sont a, b et c)'
                        }
                    },
                    {
                        'title': 'Types de contraintes',
                        'type': 'list',
                        'items': [
                            {'code': '~', 'text': 'Valeur initiale (ex: center~5)'},
                            {'code': '=', 'text': 'Valeur fixe (ex: amplitude=3)'},
                            {'code': '>', 'text': 'Borne inférieure (ex: sigma>0)'},
                            {'code': '<', 'text': 'Borne supérieure (ex: center<10)'}
                        ]
                    },
                    {
                        'title': 'Relations entre paramètres',
                        'type': 'list',
                        'items': [
                            {'code': '|', 'text': 'Définit des relations entre paramètres (après les paramètres)'},
                            {'code': 'même modèle', 'text': 'a=2*b (utilise les paramètres du même modèle)'},
                            {'code': 'modèles différents',
                             'text': 'center=L1center+10 (utilise les paramètres d\'autres modèles)'}
                        ]
                    },
                    {
                        'title': 'Syntaxe générale',
                        'type': 'code_list',
                        'items': [
                            'NOM:TYPE(PARAMETRES)',
                            'NOM:TYPE(PARAMETRES | RELATIONS)',
                            'NOM:EXPRESSION(PARAMETRES)',
                            'NOM:EXPRESSION(PARAMETRES | RELATIONS)'
                        ]
                    },
                    {
                        'title': 'Exemples simples',
                        'type': 'code_list',
                        'items': [
                            'L1:lorentzian(center~0, amplitude~5)',
                            'G1:gaussian(center=10, sigma>0)',
                            'C:constant(c~0.5)',
                            'P1:ax^2 + bx + c(a~1, b~0, c~0)'
                        ]
                    },
                    {
                        'title': 'Exemples avec relations',
                        'type': 'code_list',
                        'items': [
                            'L1:lorentzian(center~0, amplitude~5) + L2:lorentzian(center~10 | center=L1center+10)',
                            'G1:gaussian(center~0, sigma~1) + P1:ax^2 + bx + c(a, b, c | a=2*b, c=G1sigma)',
                            'L1:lorentzian(center~0) + L2:lorentzian(center~10 | amplitude=2*L1amplitude)'
                        ]
                    },
                    {
                        'title': 'Exemple complet',
                        'type': 'code_list',
                        'items': [
                            'L1:lorentzian(center~0, amplitude~5, sigma~1) + L2:lorentzian(center~10, amplitude~2, sigma~1.5 | center=L1center+10) + G1:gaussian(center~20, amplitude~4, sigma~2) + P1:ax^3 + bx^2 + cx + d(a=2, b, c~3, d | a=2*b, c=b+d)'
                        ]
                    },
                    {
                        'title': 'Fonctions supportées (expressions personnalisées)',
                        'type': 'inline_list',
                        'items': ['sin', 'cos', 'tan', 'exp', 'log', 'sqrt', 'sinh', 'cosh', 'tanh', 'arcsin', 'arccos',
                                  'arctan']
                    },
                    {
                        'title': 'Notes importantes',
                        'type': 'list',
                        'items': [
                            {'code': 'Noms',
                             'text': 'Les noms des modèles doivent commencer par une lettre (L1, G1, P1, etc.)'},
                            {'code': 'Espaces', 'text': 'Les espaces sont ignorés dans l\'expression'},
                            {'code': 'Multiplication', 'text': 'ax est équivalent à a*x'},
                            {'code': 'Puissance', 'text': 'x^2 est équivalent à x**2'},
                            {'code': 'Relations', 'text': 'Les relations sont évaluées dans l\'ordre de définition'},
                            {'code': 'Valeurs par défaut',
                             'text': 'Les paramètres sans contrainte prennent 1.0 comme valeur par défaut'}
                        ]
                    }
                ]
            }
        }
        return models_info

    def get_expression_help(self) -> str:
        """Retourne l'aide détaillée sur la syntaxe des expressions de fit"""
        help_text = """
    === Guide des Expressions de Fit ===

    1. Syntaxe Générale
    ------------------
    Une expression de fit est composée de plusieurs composants séparés par '+', chaque composant ayant la forme :
        NOM:TYPE(PARAMETRES | RELATIONS)

    2. Modèles Standards
    ------------------
    Les modèles standards sont prédéfinis et incluent :
    - Lorentzienne : L1:lorentzian(center~0, amplitude~5, sigma~1)
    - Gaussienne   : G1:gaussian(center~0, amplitude~5, sigma~1)
    - Voigt        : V1:voigt(center~0, amplitude~5, sigma~1, gamma~1)
    - Constante    : C1:constant(c~1)
    - Linéaire     : Lin1:linear(slope~1, intercept~0)

    Paramètres disponibles pour chaque type :
    * Lorentzienne/Gaussienne :
      - center    : position du pic
      - amplitude : aire sous la courbe
      - sigma     : largeur
      - fwhm      : largeur à mi-hauteur (calculée)
      - height    : hauteur du pic (calculée)

    3. Modèles Personnalisés
    ----------------------
    Vous pouvez définir vos propres expressions mathématiques :
        P1:ax^3 + bx^2 + cx + d(a=2, b~1, c~3, d<10)

    Opérations supportées :
    - Opérateurs : +, -, *, /, ^, **
    - Fonctions  : sin, cos, tan, exp, log, sqrt
    - Variables  : x (variable indépendante) et paramètres nommés

    4. Contraintes sur les Paramètres
    ------------------------------
    Plusieurs types de contraintes sont disponibles :
    - Valeur fixe     : param=valeur    (ex: a=2)
    - Valeur initiale : param~valeur    (ex: b~1)
    - Borne minimale  : param>valeur    (ex: c>0)
    - Borne maximale  : param<valeur    (ex: d<10)
    - Sans contrainte : param           (ex: e)

    5. Relations entre Paramètres
    --------------------------
    Utilisez le symbole '|' pour définir des relations entre paramètres :
        L1:lorentzian(center~0, amplitude~5) + L2:lorentzian(center~10 | center=L1center+10)
        P1:ax^2 + bx + c(a, b, c | a=2*b, c=b+1)

    Les relations peuvent utiliser :
    - Des paramètres du même modèle ou d'autres modèles
    - Des opérations arithmétiques
    - Des fonctions mathématiques

    6. Exemples Complets
    ------------------
    1. Deux lorentziennes avec relation :
       L1:lorentzian(center~0, amplitude~5, sigma~1) + 
       L2:lorentzian(center~10, amplitude~2 | center=L1center+10)

    2. Gaussienne avec contraintes :
       G1:gaussian(center>0, amplitude<10, sigma~2)

    3. Polynôme avec relations :
       P1:ax^3 + bx^2 + cx + d(a=2, b, c~3, d | b=a/2, c=b+1)

    4. Modèle complexe :
       L1:lorentzian(center~0, amplitude~5) + 
       G1:gaussian(center~10, sigma~2) + 
       P1:ax^2 + bx + c(a, b, c | a=2*b, c=G1sigma)

    Notes :
    - Les noms des composants doivent commencer par une lettre
    - Les espaces sont ignorés
    - Les relations sont évaluées dans l'ordre de définition
    - Les paramètres non contraints prennent une valeur par défaut de 1.0
    """
        return help_text

class PlotStyleBuilder:
    def __init__(self):
        self.style_expression = ""
        self.style_dict = {}

    def parse_expression(self, expression: str) -> dict:
        """
        Parse une expression de style comme:
        'template:nature;
         xaxis:log10,label="Energy (eV)",font=Arial:12pt;
         data:markers=circle:5pt:blue:0.8,line=solid:2pt:red'
        """
        style_dict = {}
        elements = expression.split(';')

        for element in elements:
            element = element.strip()
            if not element:
                continue

            if element.startswith('template:'):
                style_dict['template'] = self._parse_template(element)
            else:
                key, specs = element.split(':', 1)
                style_dict[key] = self._parse_specs(specs)

        return style_dict

    def _parse_specs(self, specs_str: str) -> dict:
        """
        Parse les spécifications d'un élément
        Ex: 'log10,label="Energy (eV)",font=Arial:12pt'
        """
        specs_dict = {}
        parts = specs_str.split(',')

        for part in parts:
            part = part.strip()
            if '=' in part:
                # Cas key=value
                key, value = part.split('=', 1)
                # Gestion des valeurs entre guillemets
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                # Gestion des valeurs multiples (ex: font=Arial:12pt)
                if ':' in value:
                    value = self._parse_value(value)
                specs_dict[key.strip()] = value
            else:
                # Cas valeur directe (ex: log10)
                specs_dict['type'] = part

        return specs_dict

    def _parse_value(self, value: str) -> dict:
        """
        Parse une valeur complexe
        Ex: 'Arial:12pt' -> {'family': 'Arial', 'size': '12pt'}
        """
        parts = value.split(':')
        if len(parts) == 1:
            return parts[0]

        # Cas spéciaux selon le type de valeur
        if 'pt' in parts[-1] or 'px' in parts[-1]:  # Taille de police
            return {
                'family': parts[0],
                'size': parts[1]
            }
        elif len(parts) == 4:  # Cas marker/line (style:size:color:alpha)
            return {
                'style': parts[0],
                'size': parts[1],
                'color': parts[2],
                'alpha': float(parts[3])
            }

        return dict(zip(['primary', 'secondary', 'tertiary'][:len(parts)], parts))

    def _parse_template(self, template_str: str) -> dict:
        """Parse un template prédéfini"""
        templates = {
            'nature': {
                'figure': {
                    'size': (89, 89),  # en mm
                    'dpi': 300,
                    'font_family': 'Arial',
                    'font_size': 8,
                    'line_width': 0.5,
                },
                'axes': {
                    'title_size': 9,
                    'label_size': 8,
                    'tick_size': 8,
                    'line_width': 0.5,
                },
                'legend': {
                    'frame_on': False,
                    'font_size': 7,
                }
            },
            'science': {
                'figure': {
                    'size': (85, 85),
                    'dpi': 300,
                    'font_family': 'Times New Roman',
                    'font_size': 9,
                },
                'axes': {
                    'title_size': 10,
                    'label_size': 9,
                    'tick_size': 9,
                    'line_width': 0.75,
                },
                'legend': {
                    'frame_on': True,
                    'font_size': 8,
                }
            }
        }
        template_name = template_str.split(':')[1]
        return templates.get(template_name, {})

    def create_style_expression(self, template: str = None, **kwargs) -> str:
        """
        Crée une expression de style
        Ex: create_style_expression('nature', xaxis={'scale': 'log10'})
        """
        parts = []
        if template:
            parts.append(f'template:{template}')

        for key, value in kwargs.items():
            if isinstance(value, dict):
                specs = ','.join(f'{k}={v}' for k, v in value.items())
                parts.append(f'{key}:{specs}')

        self.style_expression = ';'.join(parts)
        return self.style_expression

    def validate_style(self, style_dict: dict) -> bool:
        """
        Valide que le style est correctement formaté
        """
        valid_elements = {
            'xaxis': {'scale', 'label', 'ticks', 'grid'},
            'yaxis': {'scale', 'label', 'ticks', 'grid'},
            'data': {'markers', 'line', 'errorbar'},
            'figure': {'size', 'dpi', 'background', 'margins'},
            'legend': {'position', 'font', 'size', 'frame'}
        }

        for element, specs in style_dict.items():
            if element not in valid_elements and element != 'template':
                return False
            if element in valid_elements:
                if not all(key in valid_elements[element] for key in specs.keys()):
                    return False
        return True

def create_fit_fc():
    return {
        "name": "create_fit",
        "description": "Crée un nouveau fit avec des composants de base",
        "parameters": {
            "type": "object",
            "properties": {
                "components": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["lorentzian", "gaussian", "voigt", "constant", "linear"],
                                "description": "Type de modèle"
                            },
                            "count": {
                                "type": "integer",
                                "description": "Nombre de composants de ce type"
                            }
                        }
                    },
                    "description": "Liste des composants à créer"
                }
            },
            "required": ["components"]
        }
    }

def set_parameter_fc():
    return {
        "name": "set_parameter",
        "description": "Définit une contrainte sur un paramètre",
        "parameters": {
            "type": "object",
            "properties": {
                "component_id": {
                    "type": "string",
                    "description": "Identifiant du composant (ex: L1, G2)"
                },
                "parameter": {
                    "type": "string",
                    "enum": ["center", "amplitude", "sigma", "fwhm", "height"],
                    "description": "Nom du paramètre"
                },
                "constraint_type": {
                    "type": "string",
                    "enum": ["fixed", "min", "max", "initial"],
                    "description": "Type de contrainte"
                },
                "value": {
                    "type": "number",
                    "description": "Valeur de la contrainte"
                }
            },
            "required": ["component_id", "parameter", "constraint_type", "value"]
        }
    }

def add_component_fc():
    return {
        "name": "add_component",
        "description": "Ajoute un nouveau composant au fit",
        "parameters": {
            "type": "object",
            "properties": {
                "model_type": {
                    "type": "string",
                    "enum": ["lorentzian", "gaussian", "voigt", "constant", "linear"],
                    "description": "Type de modèle à ajouter"
                },
                "position": {
                    "type": "string",
                    "enum": ["start", "end"],
                    "description": "Position où ajouter le composant",
                    "default": "end"
                }
            },
            "required": ["model_type"]
        }
    }

def link_parameters_fc():
    return {
        "name": "link_parameters",
        "description": "Lie deux paramètres entre eux",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "Premier paramètre (ex: L1_center)"
                },
                "param2": {
                    "type": "string",
                    "description": "Second paramètre (ex: L2_center)"
                },
                "relation": {
                    "type": "string",
                    "enum": ["same", "offset", "ratio"],
                    "description": "Type de relation entre les paramètres"
                },
                "value": {
                    "type": "number",
                    "description": "Valeur pour la relation (offset ou ratio)",
                    "default": 0
                }
            },
            "required": ["param1", "param2", "relation"]
        }
    }

def perform_fit_fc():
    return {
        "name": "perform_fit",
        "description": "Exécute le fit avec les paramètres actuels",
        "parameters": {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["leastsq", "nelder", "powell", "cobyla", "slsqp"],
                    "description": "Méthode de minimisation",
                    "default": "leastsq"
                },
                "max_iter": {
                    "type": "integer",
                    "description": "Nombre maximum d'itérations",
                    "default": 1000
                }
            }
        }
    }

if __name__ == '__main__':
    import tkinter as tk
    from tkinter import filedialog
    import numpy as np
    import lmfit
    from scipy.integrate import quad
    from numba import jit
    from numpy import exp
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots




    @jit(nopython=True)
    def W(r, Wmax, a):
        #Version simplifiée de W pour Numba
        return Wmax * exp(-r ** 2 / a ** 2)


    def integral1(t, Wmax, a):
        #Première intégrale optimisée
        upper_limit = a * np.sqrt(-np.log(1e-10))

        def integrand(r):
            return W(r, Wmax, a) * exp(-W(r, Wmax, a) * t) * r

        return quad(integrand, 0, upper_limit, limit=200, epsabs=1e-8, epsrel=1e-8)[0]


    def integral2(t, Wmax, a):
        #Deuxième intégrale optimisée
        upper_limit = a * np.sqrt(-np.log(1e-10))

        def integrand(r):
            return (exp(-W(r, Wmax, a) * t) - 1)

        return quad(integrand, 0, upper_limit, limit=200, epsabs=1e-8, epsrel=1e-8)[0]


    @jit(nopython=True)
    def intensity_single(t, n, Wmax, a, int1, int2):
        #Version compilée du calcul final d'intensité
        return (2 * np.pi * n * int1 * exp(2 * np.pi * n * int2))


    def intensity_vectorized(times, n, Wmax, a):
        #Version vectorisée de la fonction intensité
        results = np.zeros_like(times)
        for i, t in enumerate(times):
            int1 = integral1(t, Wmax, a)
            int2 = integral2(t, Wmax, a)
            results[i] = intensity_single(t, n, Wmax, a, int1, int2)
        return results

    def fit_with_analytical(times, counts):
        """Ajustement avec seulement eta et Wmax"""

        def objective(params):
            eta = params['eta'].value
            Wmax = params['Wmax'].value
            model = intensity_vectorized(times, eta, Wmax)
            return model - counts

        # Paramètres initiaux
        params = lmfit.Parameters()
        params.add('eta', value=1.0, min=0.1, max=10.0, vary=True)
        params.add('Wmax', value=1.0, min=0.1, max=5.0, vary=True)

        # Minimisation
        min_result = lmfit.minimize(objective, params, method='least_squares')
        print(lmfit.fit_report(min_result))

        # Calcul du modèle avec les paramètres optimisés
        eta_fit = min_result.params['eta'].value
        Wmax_fit = min_result.params['Wmax'].value
        model_fit = intensity_vectorized(times, eta_fit, Wmax_fit)

        # Affichage
        fig = create_plotly_figure(times, counts, model_fit,
                                   {'eta': eta_fit, 'Wmax': Wmax_fit})
        fig.show()

        return min_result

    def open_file():
        """Ouvre une boîte de dialogue pour sélectionner un fichier .dat"""
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


    def create_plotly_figure(times, counts, model_fit, params):
        """Crée une figure Plotly avec les données et l'ajustement"""

        # Création de la figure
        fig = make_subplots(rows=2, cols=1,
                            row_heights=[0.7, 0.3],
                            vertical_spacing=0.15,
                            subplot_titles=('Ajustement de la courbe de déclin',
                                            'Résidus'))

        # Tracé des données et de l'ajustement
        fig.add_trace(
            go.Scatter(x=times, y=counts,
                       mode='markers',
                       name='Données',
                       marker=dict(size=6,
                                   color='blue',
                                   symbol='circle')),
            row=1, col=1
        )

        fig.add_trace(
            go.Scatter(x=times, y=model_fit,
                       mode='lines',
                       name='Ajustement',
                       line=dict(color='red')),
            row=1, col=1
        )

        # Calcul et tracé des résidus
        residuals = counts - model_fit
        fig.add_trace(
            go.Scatter(x=times, y=residuals,
                       mode='markers',
                       name='Résidus',
                       marker=dict(size=6,
                                   color='green',
                                   symbol='circle')),
            row=2, col=1
        )

        # Ligne horizontale à y=0 pour les résidus
        fig.add_trace(
            go.Scatter(x=[times.min(), times.max()],
                       y=[0, 0],
                       mode='lines',
                       line=dict(color='black', dash='dash'),
                       showlegend=False),
            row=2, col=1
        )

        # Configuration de la mise en page
        fig.update_layout(
            title_text=f"Ajustement de la courbe de déclin<br>n={params['n']:.2f}, a={params['a']:.2f}, Wmax={params['Wmax']:.2f}",
            showlegend=True,
            height=800,
            template='plotly_white',
            yaxis_type="log"
        )

        # Configuration des axes
        fig.update_xaxes(title_text="Temps (ns)", row=1, col=1)
        fig.update_xaxes(title_text="Temps (ns)", row=2, col=1)
        fig.update_yaxes(title_text="Counts (normalisés)", row=1, col=1)
        fig.update_yaxes(title_text="Résidus", row=2, col=1)

        return fig


    def _fit_with_analytical(times, counts):
        """Ajustement avec la solution analytique"""

        def objective(params):
            n, a, Wmax = params['n'].value, params['a'].value, params['Wmax'].value
            model = intensity_vectorized(times, n, Wmax, a)
            # Création d'un poids plus important pour les premiers points
            weights = 1.0 / (1.0 + times**2)  # Décroissance plus forte
            return (model - counts) * weights


        # Paramètres initiaux
        params = lmfit.Parameters()

        params.add('n', value=0.001, min=0.000000001, max=10.0, vary=True)
        params.add('a', value=np.sqrt(800), min=30.0, max=100.0, vary=True)
        params.add('Wmax', value=5.0, min=0.5, max=20.0, vary=True)
        #print(f"etha = {n * a * a}")
        # Minimisation
        min_result = lmfit.minimize(objective, params, method='leastsq')
        print(lmfit.fit_report(min_result))

        # Résultats
        n_fit = min_result.params['n'].value
        a_fit = min_result.params['a'].value
        Wmax_fit = min_result.params['Wmax'].value
        model_fit = intensity_vectorized(times, n_fit, Wmax_fit, a_fit)

        # Création et affichage de la figure Plotly
        params_dict = {'n': n_fit, 'a': a_fit, 'Wmax': Wmax_fit}
        fig = create_plotly_figure(times, counts, model_fit, params_dict)
        fig.show()



    # file_path = "/chemin/vers/votre/fichier.dat"
    file_path = "/home/yopla/Downloads/N3978_shutter_diaph2mm_3kV_spot3_int200s_236nm_160K.dat"

    if file_path:
        try:
            filtered_times, filtered_counts = process_data(file_path)
            fit_with_analytical(filtered_times, filtered_counts)
        except Exception as e:
            print(f"Erreur lors du traitement : {e}")






def bob():
    import numpy as np



    # Génération des données de test
    x_data = np.linspace(-10, 30, 200)
    y_data = (
        5 * 1 / (1 + ((x_data - 0) / 1)**2) +  # Première lorentzienne
        3 * 1 / (1 + ((x_data - 10) / 1.5)**2) +  # Deuxième lorentzienne
        4 * np.exp(-(x_data - 20)**2 / (2 * 2**2)) +  # Gaussienne
        0.5 +  # Constante
        np.random.normal(0, 0.1, x_data.shape)  # Bruit
    )

    # Expression de fit
    expression = """L1:lorentzian(center~0, amplitude~5, sigma~1) + 
                    L2:lorentzian(center~10, amplitude~2, sigma~1.5 | center=L1center+10, amplitude=2*L1amplitude) + 
                    G1:gaussian(center~20, amplitude~4, sigma~2 | sigma=L1sigma) + 
                    P1:ax^3 + bx^2 + cx + d(a=2, b, c~3, d | a=2*b, c=b+d)"""

    # Utilisation
    fit_mgr = AdvancedFitManager()
    # Style Nature Communication
    style_expr = """
    xaxis:type=log10,title="Energy (eV)",showgrid=true,gridcolor="#EEEEEE";
    yaxis:type=linear,title="Intensity (a.u.)",showgrid=true;
    legend:position=top-right,borderwidth=0;
    figure:width=800,height=600,bgcolor="white"
    """

    fit_mgr.set_data(x_data, y_data)
    fit_mgr.setup_from_expression(expression)
    fit_mgr.fit() # method='nelder', max_nfev=1000
    fig, config = fit_mgr.plot_result(show_components=False, template="web", add_controls=False)

    fig.show(config=config)

    print(fit_mgr.get_fit_report())

"""
# Création du builder
builder = FitBuilder()

# Construction de l'expression
builder.create_base_expression([('lorentzian', 2), ('gaussian', 1)])
builder.set_parameter_constraint('L1', 'center', 'fixed', 5.0)

# Création du fit manager avec l'expression
fit_manager = builder.build_fit()

# Utilisation du fit manager
fit_manager.set_data(x_data, y_data)
fit_manager.fit()
fit_manager.plot_result()
print(fit_manager.get_fit_report())
"""