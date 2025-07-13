from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout, get_user_model
from django.contrib import messages
from django.db import models
from .models import Estoque, Produto, Categoria, Movimentacao, Metrica
from .forms import ProdutoForm, CategoriaForm, CustomUserCreationForm, EstoqueForm
from django.http import JsonResponse, HttpResponseForbidden
from django.urls import reverse

def login_usuario(request):
    if request.user.is_authenticated:
        return redirect('selecionar_estoque')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('selecionar_estoque')
        else:
            messages.error(request, 'Usuário ou senha inválidos.')
    else:
        form = AuthenticationForm()
    return render(request, 'App/login.html', {'form': form})

def cadastro_usuario(request):
    if request.user.is_authenticated:
        return redirect('selecionar_estoque')
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('selecionar_estoque')
        else:
            messages.error(request, 'Corrija os erros abaixo.')
    else:
        form = CustomUserCreationForm()
    return render(request, 'App/cadastro_usuario.html', {'form': form})

from .models import CompraRecorrente

@login_required
def usuario_configuracao(request):
    aba = request.GET.get('aba', 'dados')  # 'dados', 'privacidade', 'deletar'
    context = {'aba': aba}
    return render(request, 'App/configuracao_usuario.html', context)

@login_required
def logout_usuario(request):
    # Resetar o campo ignorar_ate_logout para todas as compras recorrentes do usuário
    CompraRecorrente.objects.filter(ignorar_ate_logout=True).update(ignorar_ate_logout=False)
    logout(request)
    return redirect('login')

@login_required
def deletar_usuario(request):
    if request.method == 'POST':
        user = request.user
        estoques = user.estoques.all()
        for estoque in estoques:
            if estoque.usuarios.count() > 1:
                estoque.usuarios.remove(user)
            else:
                estoque.delete()
        logout(request)
        user.delete()
        messages.success(request, "Sua conta foi deletada com sucesso.")
        return redirect('login')
    return redirect('usuario_configuracao')

@login_required
def criar_estoque(request):
    if request.method == 'POST':
        form = EstoqueForm(request.POST, usuario_atual=request.user)
        if form.is_valid():
            estoque = form.save(commit=False)
            estoque.save()
            # Sempre adiciona o usuário atual
            estoque.usuarios.add(request.user)
            # Adiciona outros usuários selecionados
            for u in form.cleaned_data['usuarios']:
                estoque.usuarios.add(u)
            return redirect('selecionar_estoque')
    else:
        form = EstoqueForm(usuario_atual=request.user)
    return render(request, 'App/gerenciar_estoque.html', {'pagina': 'novo', 'form': form})

@login_required
def selecionar_estoque(request):
    estoques = request.user.estoques.all().prefetch_related('usuarios')
    if request.method == 'POST':
        estoque_id = request.POST.get('estoque_id')
        if estoque_id:
            return redirect('estoque_dashboard', estoque_id=estoque_id)
    return render(request, 'App/gerenciar_estoque.html', {'pagina': 'selecionar', 'estoques': estoques})

@login_required
def editar_estoque(request, estoque_id):
    estoque = get_object_or_404(Estoque, id=estoque_id, usuarios=request.user)
    if request.method == 'POST':
        form = EstoqueForm(request.POST, instance=estoque, usuario_atual=request.user)
        if form.is_valid():
            estoque = form.save(commit=False)
            estoque.save()
            usuarios = list(form.cleaned_data['usuarios'])
            # Garante que o usuário atual nunca seja removido do estoque
            if request.user not in usuarios:
                usuarios.append(request.user)
            estoque.usuarios.set(usuarios)
            messages.success(request, "Estoque atualizado com sucesso.")
            return redirect('selecionar_estoque')
    else:
        form = EstoqueForm(instance=estoque, usuario_atual=request.user)
    # AQUI ESTÁ O AJUSTE: usa o mesmo template da listagem e passa a flag 'pagina'
    return render(
        request,
        'App/gerenciar_estoque.html',
        {
            'pagina': 'editar',
            'form': form,
            'estoque': estoque,
        }
    )

@login_required
def remover_usuario_do_estoque(request, estoque_id, user_id):
    estoque = get_object_or_404(Estoque, id=estoque_id)
    User = get_user_model()
    user = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        if estoque.usuarios.count() > 1:
            estoque.usuarios.remove(user)
            removed = True
            deleted = False
        else:
            estoque.delete()
            removed = False
            deleted = True
        return JsonResponse({
            "success": True,
            "removed": removed,
            "deleted": deleted,
            "estoque_id": estoque_id,
            "user_id": user_id,
        })
    return JsonResponse({"error": "Método não permitido."}, status=405)

@login_required
def estoque_dashboard(request, estoque_id):
    estoque = get_object_or_404(Estoque, id=estoque_id, usuarios=request.user)
    produtos = estoque.produtos.select_related('categoria').all()
    compras_recorrentes = CompraRecorrente.objects.filter(produto__estoque=estoque)
    avisos_recorrentes = []

    aba = request.GET.get('aba')  # <- CAPTURA ABA
    if not aba:
        aba = 'produtos'

    # Gerenciamento de categorias (POST dentro do dashboard)
    categorias = estoque.categorias.all()
    categoria_form = None
    metricas = Metrica.objects.all().order_by('-fixa', 'nome')

    if aba == 'categorias':
        # Nova Categoria: mostrar formulário vazio
        if request.method == 'POST' and request.POST.get('nova_categoria'):
            categoria_form = CategoriaForm()
        # Salvar categoria nova ou edição
        elif request.method == 'POST' and (request.POST.get('nome') or request.POST.get('id')):
            cat_id = request.GET.get('cat_edit') or request.POST.get('id')
            if cat_id:
                categoria = get_object_or_404(Categoria, id=cat_id, estoque=estoque)
                categoria_form = CategoriaForm(request.POST, instance=categoria)
            else:
                categoria_form = CategoriaForm(request.POST)
            if categoria_form.is_valid():
                cat = categoria_form.save(commit=False)
                cat.estoque = estoque
                cat.save()
                return redirect(f"{reverse('estoque_dashboard', args=[estoque.id])}?aba=categorias")
        # Excluir categoria
        elif request.method == 'POST' and request.POST.get('cat_delete'):
            categoria = get_object_or_404(Categoria, id=request.POST['cat_delete'], estoque=estoque)
            categoria.delete()
            return redirect(f"{reverse('estoque_dashboard', args=[estoque.id])}?aba=categorias")
        # Edição de categoria
        elif request.GET.get('cat_edit'):
            categoria = get_object_or_404(Categoria, id=request.GET['cat_edit'], estoque=estoque)
            categoria_form = CategoriaForm(instance=categoria)

    # Criação de produto (POST dentro do dashboard)
    form_produto = ProdutoForm(estoque=estoque)
    if aba == 'criar_produto':
        if request.method == 'POST':
            form_produto = ProdutoForm(request.POST, estoque=estoque)
            if form_produto.is_valid():
                produto = form_produto.save(commit=False)
                produto.estoque = estoque
                quantidade_inicial = produto.unidades or 0
                produto.unidades = 0
                produto.save()
                if quantidade_inicial > 0:
                    Movimentacao.objects.create(
                        produto=produto,
                        tipo=Movimentacao.ENTRADA,
                        quantidade=quantidade_inicial
                    )
                if form_produto.cleaned_data.get('criar_compra_recorrente'):
                    CompraRecorrente.objects.create(
                        produto=produto,
                        cota_minima=form_produto.cleaned_data.get('cota_minima', 0),
                        checar_periodicamente=form_produto.cleaned_data.get('checar_periodicamente', True)
                    )
                return redirect(f"{reverse('estoque_dashboard', args=[estoque.id])}?aba=produtos")

    # Filtros de pesquisa dos produtos
    q = request.GET.get('q', '').strip()
    categoria_id = request.GET.get('categoria', '')
    marca = request.GET.get('marca', '').strip()
    metrica_id = request.GET.get('metrica', '').strip()
    created_op = request.GET.get('created_op')
    created_val = request.GET.get('created_val')
    updated_op = request.GET.get('updated_op')
    updated_val = request.GET.get('updated_val')
    preco_total_op = request.GET.get('preco_total_op')
    preco_total_val = request.GET.get('preco_total_val')

    marcas = produtos.exclude(marca='').values_list('marca', flat=True).distinct().order_by('marca')

    if q:
        produtos = produtos.filter(nome__icontains=q)
    if categoria_id:
        produtos = produtos.filter(categoria__id=categoria_id)
    if marca:
        produtos = produtos.filter(marca=marca)
    if metrica_id:
        produtos = produtos.filter(metrica__id=metrica_id)
    if created_op and created_val:
        if created_op == 'lt':
            produtos = produtos.filter(created_at__date__lt=created_val)
        elif created_op == 'eq':
            produtos = produtos.filter(created_at__date=created_val)
        elif created_op == 'gt':
            produtos = produtos.filter(created_at__date__gt=created_val)
    if updated_op and updated_val:
        if updated_op == 'lt':
            produtos = produtos.filter(updated_at__date__lt=updated_val)
        elif updated_op == 'eq':
            produtos = produtos.filter(updated_at__date=updated_val)
        elif updated_op == 'gt':
            produtos = produtos.filter(updated_at__date__gt=updated_val)

    produtos_info = []
    for produto in produtos:
        entradas = Movimentacao.objects.filter(produto=produto, tipo=Movimentacao.ENTRADA).aggregate(total=models.Sum('quantidade'))['total'] or 0
        saidas = Movimentacao.objects.filter(produto=produto, tipo=Movimentacao.SAIDA).aggregate(total=models.Sum('quantidade'))['total'] or 0
        saldo = entradas - saidas
        preco_total = produto.preco * saldo
        produtos_info.append({
            'produto': produto,
            'saldo': saldo,
            'preco_total': preco_total,
        })
    if preco_total_op and preco_total_val:
        try:
            preco_total_val = float(preco_total_val)
            if preco_total_op == 'lt':
                produtos_info = [pi for pi in produtos_info if pi['preco_total'] < preco_total_val]
            elif preco_total_op == 'eq':
                produtos_info = [pi for pi in produtos_info if pi['preco_total'] == preco_total_val]
            elif preco_total_op == 'gt':
                produtos_info = [pi for pi in produtos_info if pi['preco_total'] > preco_total_val]
        except ValueError:
            pass

    # AVISOS RECORRENTES - Simplified logic: only check quota and if periodic checking is enabled
    for compra in compras_recorrentes:
        if compra.checar_periodicamente and not compra.ignorar_ate_logout:
            produto = compra.produto
            saldo = Movimentacao.objects.filter(produto=produto, tipo=Movimentacao.ENTRADA).aggregate(
                total=models.Sum('quantidade'))['total'] or 0
            saldo -= Movimentacao.objects.filter(produto=produto, tipo=Movimentacao.SAIDA).aggregate(
                total=models.Sum('quantidade'))['total'] or 0
            if compra.cota_minima > 0 and saldo < compra.cota_minima:
                avisos_recorrentes.append({
                    'compra_id': compra.id,
                    'produto_nome': produto.nome,
                    'saldo_atual': saldo,
                    'minimo': compra.cota_minima,
                })
    # CONTEXTO FINAL
    context = {
        'estoque': estoque,
        'aba': aba,
        'produtos_info': produtos_info,
        'marcas': marcas,
        'avisos_recorrentes': avisos_recorrentes,
        'categorias': categorias,
        'form': form_produto,  # Para {% include "App/produto_criar_include.html" %}
        'categoria_form': categoria_form,
        'metricas': metricas,
    }
    return render(request, 'App/estoque_dashboard.html', context)

@login_required
def produto_create(request, estoque_id):
    estoque = get_object_or_404(Estoque, id=estoque_id, usuarios=request.user)
    if request.method == 'POST':
        form = ProdutoForm(request.POST, estoque=estoque)
        if form.is_valid():
            produto = form.save(commit=False)
            produto.estoque = estoque
            quantidade_inicial = produto.unidades or 0  # Salva o valor informado
            produto.unidades = 0  # Zera o campo, saldo será só via movimentações
            produto.save()
            if quantidade_inicial > 0:
                Movimentacao.objects.create(
                    produto=produto,
                    tipo=Movimentacao.ENTRADA,
                    quantidade=quantidade_inicial
                )
            if form.cleaned_data.get('criar_compra_recorrente'):
                CompraRecorrente.objects.create(
                    produto=produto,
                    cota_minima=form.cleaned_data.get('cota_minima', 0),
                    checar_periodicamente=form.cleaned_data.get('checar_periodicamente', True)
                )
            return redirect('estoque_dashboard', estoque_id=estoque.id)
    else:
        form = ProdutoForm(estoque=estoque)
    return render(request, 'App/produto_form.html', {'form': form, 'estoque': estoque})

@login_required
def produto_update(request, estoque_id, produto_id):
    estoque = get_object_or_404(Estoque, id=estoque_id, usuarios=request.user)
    produto = get_object_or_404(Produto, id=produto_id, estoque=estoque)

    try:
        compra_recorrente = produto.compras_recorrentes.first()
    except AttributeError:
        compra_recorrente = None

    if request.method == 'POST':
        form = ProdutoForm(request.POST, instance=produto, estoque=estoque)
        if form.is_valid():
            # 1. Calcule o saldo atual do produto
            entradas = Movimentacao.objects.filter(produto=produto, tipo=Movimentacao.ENTRADA).aggregate(total=models.Sum('quantidade'))['total'] or 0
            saidas = Movimentacao.objects.filter(produto=produto, tipo=Movimentacao.SAIDA).aggregate(total=models.Sum('quantidade'))['total'] or 0
            saldo_atual = entradas - saidas

            # 2. Novo saldo desejado informado no campo unidades
            novo_saldo = form.cleaned_data['unidades']

            # 3. Diferenca entre novo e atual
            diff = novo_saldo - saldo_atual

            produto = form.save(commit=False)
            produto.save()

            # 4. Cria movimentação automática de ajuste de saldo
            if diff != 0:
                Movimentacao.objects.create(
                    produto=produto,
                    tipo=Movimentacao.ENTRADA if diff > 0 else Movimentacao.SAIDA,
                    quantidade=abs(diff)
                )

            # Compra recorrente simplified logic
            if form.cleaned_data.get('criar_compra_recorrente'):
                if compra_recorrente:
                    compra_recorrente.cota_minima = form.cleaned_data.get('cota_minima', 0)
                    compra_recorrente.checar_periodicamente = form.cleaned_data.get('checar_periodicamente', True)
                    compra_recorrente.ignorar_ate_logout = False
                    compra_recorrente.save()
                else:
                    CompraRecorrente.objects.create(
                        produto=produto,
                        cota_minima=form.cleaned_data.get('cota_minima', 0),
                        checar_periodicamente=form.cleaned_data.get('checar_periodicamente', True)
                    )
            elif compra_recorrente:
                compra_recorrente.delete()
            return redirect('estoque_dashboard', estoque_id=estoque.id)
    else:
        initial = {}

        if compra_recorrente:
            initial.update({
                'criar_compra_recorrente': True,
                'cota_minima': compra_recorrente.cota_minima,
                'checar_periodicamente': compra_recorrente.checar_periodicamente
            })

        form = ProdutoForm(instance=produto, estoque=estoque, initial=initial)

    return render(request, 'App/produto_form.html', {'form': form, 'estoque': estoque, 'produto': produto})

@login_required
def produto_delete(request, estoque_id, produto_id):
    estoque = get_object_or_404(Estoque, id=estoque_id, usuarios=request.user)
    try:
        produto = Produto.objects.get(pk=produto_id)
    except Produto.DoesNotExist:
        messages.warning(request, "O produto não existe ou já foi excluído.")
        return redirect('estoque_dashboard')
    if request.method == 'POST':
        produto.delete()
        return redirect('estoque_dashboard', estoque_id=estoque.id)
    return render(request, 'App/produto_confirm_delete.html', {'produto': produto, 'estoque': estoque})

@login_required
def categoria_create(request, estoque_id):
    estoque = get_object_or_404(Estoque, id=estoque_id, usuarios=request.user)
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            categoria = form.save(commit=False)
            categoria.estoque = estoque
            categoria.save()
            return redirect('estoque_dashboard', estoque_id=estoque.id)
    else:
        form = CategoriaForm()
    return render(request, 'App/categoria_form.html', {'form': form, 'estoque': estoque})

@login_required
def categorias_gerenciar(request, estoque_id):
    estoque = get_object_or_404(Estoque, id=estoque_id, usuarios=request.user)
    if request.method == 'POST':
        nome = request.POST.get('nome_categoria')
        if nome:
            Categoria.objects.create(estoque=estoque, nome=nome)
            return redirect('categorias_gerenciar', estoque_id=estoque.id)
    categorias = estoque.categorias.all()
    return render(request, 'App/categorias_gerenciar.html', {'estoque': estoque, 'categorias': categorias})

@login_required
def categoria_update(request, estoque_id, categoria_id):
    estoque = get_object_or_404(Estoque, id=estoque_id, usuarios=request.user)
    categoria = get_object_or_404(Categoria, id=categoria_id, estoque=estoque)
    if request.method == 'POST':
        form = CategoriaForm(request.POST, instance=categoria)
        if form.is_valid():
            form.save()
            return redirect('estoque_dashboard', estoque_id=estoque.id)
    else:
        form = CategoriaForm(instance=categoria)
    return render(request, 'App/categoria_form.html', {'form': form, 'estoque': estoque, 'categoria': categoria})


@login_required
def categoria_delete(request, estoque_id, categoria_id):
    estoque = get_object_or_404(Estoque, id=estoque_id, usuarios=request.user)
    categoria = get_object_or_404(Categoria, id=categoria_id, estoque=estoque)
    if request.method == 'POST':
        categoria.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return redirect('estoque_dashboard', estoque_id=estoque.id)
    return JsonResponse({'error': 'Metodo nao permitido.'}, status=405)

@login_required
@csrf_exempt
def ignorar_compra_recorrente(request, compra_id):
    if request.method == 'POST':
        compra = get_object_or_404(CompraRecorrente, id=compra_id)
        compra.ignorar_ate_logout = True
        compra.save()
        return JsonResponse({'sucesso': True})
    return JsonResponse({'erro': 'Método não permitido.'}, status=405)

@login_required
def marcar_compra_realizada(request, compra_id):
    # This method is deprecated in the simplified recurring purchase system
    # We no longer track purchase dates, just stock levels
    if request.method == "POST":
        try:
            compra = CompraRecorrente.objects.get(pk=compra_id)
            # Instead of updating dates, we just remove the ignore flag
            compra.ignorar_ate_logout = False
            compra.save()
            return JsonResponse({"sucesso": True})
        except CompraRecorrente.DoesNotExist:
            return JsonResponse({"sucesso": False, "erro": "Compra não encontrada."})
    return HttpResponseForbidden()