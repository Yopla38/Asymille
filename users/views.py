import base64
import io
import json

import numpy as np
import plotly
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
# Configurer le backend pour matplotlib avant l'importation de pyplot
import matplotlib
from django.views.decorators.http import require_http_methods

matplotlib.use('Agg')  # Utilise un backend non-GUI adapté pour le web
import matplotlib.pyplot as plt
from matplotlib.backends.backend_template import FigureCanvas
from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .fit import FitForm
from .models import User, FitSession
from .serializers import UserSerializer
import stripe
from django.conf import settings
from fit_builder.fit import FitBuilder, AdvancedFitManager  # Assurez-vous que votre FitBuilder est accessible


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]


stripe.api_key = settings.STRIPE_SECRET_KEY


def home(request):
    return render(request, 'users/home.html')


@api_view(['POST'])
def create_payment(request):
    amount = request.data.get('amount')
    payment_intent = stripe.PaymentIntent.create(
        amount=int(amount * 100),
        currency='usd',
        payment_method_types=['card'],
    )
    return Response({'client_secret': payment_intent.client_secret})


# Ajoutez ces vues pour la gestion AJAX des sessions
@login_required
@require_http_methods(["POST"])
def save_session_state(request):
    try:
        session_id = request.POST.get('session_id')
        session = FitSession.objects.get(id=session_id, user=request.user)

        # Mise à jour des objets personnalisés
        if 'custom_objects' in request.POST:
            session.custom_objects = json.loads(request.POST['custom_objects'])

        # Mise à jour du template
        if 'template' in request.POST:
            session.template = json.loads(request.POST['template'])

        # Mise à jour de la configuration du graphique
        if 'plot_config' in request.POST:
            session.plot_config = json.loads(request.POST['plot_config'])

        session.save()

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["GET"])
def load_session_state(request, session_id):
    try:
        session = FitSession.objects.get(id=session_id, user=request.user)
        return JsonResponse({
            'success': True,
            'state': session.get_plot_state()
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def create_session(request):
    try:
        data = json.loads(request.body)
        name = data.get('name', '')

        session = FitSession.objects.create(
            user=request.user,
            name=name,
            expression="",  # Expression vide par défaut
            fit_report=""  # Rapport vide par défaut
        )

        return JsonResponse({
            'success': True,
            'session_id': session.id
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(["DELETE"])
def delete_session(request):
    try:
        session_id = request.GET.get('session_id')
        session = FitSession.objects.get(id=session_id, user=request.user)
        session.delete()

        return JsonResponse({
            'success': True
        })
    except FitSession.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Session non trouvée'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required(login_url='account_login')
def fit_view(request):
    fit_manager = AdvancedFitManager()
    models_info = fit_manager.get_available_models()
    session_id = request.GET.get('session_id')
    current_session = None

    # Contexte de base
    context = {
        'models_info': models_info,
        'sessions': FitSession.objects.filter(user=request.user).order_by("-created_at"),
    }

    if session_id:
        try:
            current_session = FitSession.objects.get(id=session_id, user=request.user)
            context['current_session'] = current_session
        except FitSession.DoesNotExist:
            messages.error(request, "Session non trouvée.")

    if request.method == 'POST':
        form = FitForm(request.POST)
        if form.is_valid():

            try:
                all_fits = []
                data_json = form.cleaned_data.get('data')
                data_dict = json.loads(data_json)
                # Debug
                print("Données reçues:", data_dict)
                print("Colonnes sélectionnées - X:", data_dict.get('x_column'), "Y:", data_dict.get('y_column'))
                print("En-têtes:", data_dict.get('headers'))

                # Récupérer et parser l'intervalle de fit
                fit_range_str = request.POST.get('fit_range', '{}')
                fit_range = json.loads(fit_range_str) if fit_range_str else {}


                if data_json:
                    data_dict = json.loads(data_json)
                    # Créer ou mettre à jour la session
                    if not current_session:
                        current_session = FitSession(user=request.user)

                    # Sauvegarder l'état des données
                    current_session.save_data_state(data_dict)
                    pages = data_dict.get('pages', []) if isinstance(data_dict, dict) else data_dict
                    x_column = int(data_dict.get('x_column', 0))
                    y_column = int(data_dict.get('y_column', 1))

                    print(f"Colonnes sélectionnées - X: {x_column}, Y: {y_column}")

                    # Sauvegarder l'intervalle de fit
                    current_session.fit_range = fit_range
                    current_session.save()

                    for page_num, current_page in enumerate(pages):
                        if current_page and len(current_page) > 0:
                            try:
                                valid_rows = []
                                for row in current_page:
                                    if len(row) > max(x_column, y_column):
                                        try:
                                            x = float(row[x_column])
                                            y = float(row[y_column])
                                            valid_rows.append([x, y])
                                        except (ValueError, TypeError):
                                            continue

                                if valid_rows:
                                    data_array = np.array(valid_rows)
                                    x_column = data_dict.get('x_column', 0)
                                    y_column = data_dict.get('y_column', 1)
                                    headers = data_dict.get('headers', [])
                                    x_data = data_array[:, 0]
                                    y_data = data_array[:, 1]

                                    # Données complètes pour le tracé
                                    x_data_full = x_data.copy()
                                    y_data_full = y_data.copy()

                                    if fit_range.get('enabled'):
                                        # Filtrer les données selon l'intervalle
                                        x_min = fit_range.get('min')
                                        x_max = fit_range.get('max')
                                        if x_min is not None and x_max is not None:
                                            mask = (x_data >= x_min) & (x_data <= x_max)
                                            x_data = x_data[mask]
                                            y_data = y_data[mask]

                                    # Fit
                                    fit_manager = AdvancedFitManager()
                                    fit_manager.setup_from_expression(form.cleaned_data['expression'])
                                    fit_manager.set_data(x_data, y_data)
                                    fit_manager.fit()

                                    # Plot
                                    fig, config = fit_manager.plot_result(show_components=True, template="web",
                                                                          add_controls=False)

                                    # Mettre à jour les données expérimentales (première trace)
                                    if len(fig.data) > 0:
                                        # Vérifier que la première trace a bien des données x et y
                                        if hasattr(fig.data[0], 'x') and hasattr(fig.data[0], 'y'):
                                            fig.data[0].x = x_data_full
                                            fig.data[0].y = y_data_full
                                        else:
                                            print("Warning: La première trace n'a pas le format attendu")

                                    '''
                                    # Pour tracer l'interval
                                    if fit_range.get('enabled'):
                                        # Ajuster les paramètres du graphique pour montrer l'intervalle de fit
                                        fig.add_vrect(x0=x_min, x1=x_max,
                                                      fillcolor="rgba(0,0,255,0.1)",
                                                      layer="below",
                                                      line_width=0)
                                    '''

                                    fig.update_layout(
                                        xaxis_title={'text': headers[x_column]},
                                        yaxis_title={'text': headers[y_column]}
                                    )

                                    plot_json = json.dumps({
                                        'data': fig.data,
                                        'layout': fig.layout,
                                        'config': config
                                    }, cls=plotly.utils.PlotlyJSONEncoder)

                                    all_fits.append({
                                        'page': page_num + 1,
                                        'plot_json': plot_json,
                                        'fit_report': fit_manager.get_fit_report()
                                    })

                            except Exception as e:
                                print(f"Erreur lors du traitement de la page {page_num + 1}: {str(e)}")
                                continue

                # Si aucun fit n'a réussi, utiliser les données de test
                if not all_fits:
                    # Votre code existant pour les données de test...
                    x_data = np.linspace(-10, 30, 200)
                    y_data = (
                            5 * 1 / (1 + ((x_data - 0) / 1) ** 2) +
                            3 * 1 / (1 + ((x_data - 10) / 1.5) ** 2) +
                            4 * np.exp(-(x_data - 20) ** 2 / (2 * 2 ** 2)) +
                            0.5 +
                            np.random.normal(0, 0.1, x_data.shape)
                    )

                    fit_manager = AdvancedFitManager()
                    fit_manager.setup_from_expression(form.cleaned_data['expression'])
                    fit_manager.set_data(x_data, y_data)
                    fit_manager.fit()

                    fig, config = fit_manager.plot_result(show_components=True, template="web", add_controls=True)
                    plot_json = json.dumps({
                        'data': fig.data,
                        'layout': fig.layout,
                        'config': config
                    }, cls=plotly.utils.PlotlyJSONEncoder)

                    all_fits.append({
                        'page': 'Test',
                        'plot_json': plot_json,
                        'fit_report': fit_manager.get_fit_report()
                    })

                # Sauvegarder la session
                if not current_session:
                    current_session = FitSession(user=request.user)

                current_session.expression = form.cleaned_data['expression']
                #current_session.data = json.loads(data_json)
                current_session.fit_report = all_fits[-1]['fit_report']
                current_session.plot_config = json.loads(all_fits[-1]['plot_json'])

                if request.POST.get('custom_objects'):
                    current_session.custom_objects = json.loads(request.POST.get('custom_objects'))
                if request.POST.get('template'):
                    current_session.template = json.loads(request.POST.get('template'))

                current_session.save()

                # Mettre à jour le contexte avec les résultats
                context.update({
                    'form': form,
                    'all_fits': all_fits,
                    'current_session': current_session,
                    'fit_range': current_session.fit_range if current_session else {}
                })

                return render(request, 'users/fit.html', context)

            except Exception as e:
                messages.error(request, f"Erreur lors du traitement: {str(e)}")
                context['form'] = form
                context['fit_range'] = current_session.fit_range if current_session else {}
                return render(request, 'users/fit.html', context)
    else:
        # GET request
        if current_session:
            context['fit_range'] = json.dumps(getattr(current_session, 'fit_range', {}))
            # Restaurer les données de la session
            data_state = current_session.get_data_state()
            form = FitForm(initial={
                'expression': current_session.expression,
                'data': json.dumps(data_state)
            })

            # Ajouter les données au contexte
            context.update({
                'data_state': data_state,
                'active_page': current_session.active_page,
                'fit_range': current_session.fit_range if current_session else {}
            })

            # Restaurer le dernier fit si disponible
            if current_session.plot_config:
                all_fits = [{
                    'page': 1,
                    'plot_json': json.dumps(current_session.plot_config),
                    'fit_report': current_session.fit_report
                }]
                context['all_fits'] = all_fits
        else:
            form = FitForm()

    context['form'] = form
    return render(request, 'users/fit.html', context)

