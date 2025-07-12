from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_usuario, name='login'),
    path('cadastro/', views.cadastro_usuario, name='cadastro'),
    path('configuracoes/', views.usuario_configuracao, name='usuario_configuracao'),
    path('configuracoes/deletar/', views.deletar_usuario, name='deletar_usuario'),
    path('logout/', views.logout_usuario, name='logout'),
    path('estoque/novo/', views.criar_estoque, name='criar_estoque'),
    path('estoque/<int:estoque_id>/editar/', views.editar_estoque, name='editar_estoque'),
    #path('estoque/<int:estoque_id>/remover/', views.remover_estoque, name='remover_estoque'),
    path('estoque/<int:estoque_id>/usuario/<int:user_id>/remover/', views.remover_usuario_do_estoque, name='remover_usuario_do_estoque'),
    path('estoques/', views.selecionar_estoque, name='selecionar_estoque'),
    path('estoque/<int:estoque_id>/dashboard/', views.estoque_dashboard, name='estoque_dashboard'),
    path('estoque/<int:estoque_id>/produto/novo/', views.produto_create, name='produto_create'),
    path('estoque/<int:estoque_id>/produto/<int:produto_id>/editar/', views.produto_update, name='produto_update'),
    path('estoque/<int:estoque_id>/produto/<int:produto_id>/remover/', views.produto_delete, name='produto_delete'),
    path('estoque/<int:estoque_id>/categorias/', views.categorias_gerenciar, name='categorias_gerenciar'),
    path('estoque/<int:estoque_id>/categoria/novo/', views.categoria_create, name='categoria_create'),
    path('estoque/<int:estoque_id>/categoria/<int:categoria_id>/editar/', views.categoria_update, name='categoria_update'),
    path('estoque/<int:estoque_id>/categoria/<int:categoria_id>/remover/', views.categoria_delete, name='categoria_delete'),
    path('compras_recorrentes/<int:compra_id>/ignorar/', views.ignorar_compra_recorrente, name='ignorar_compra_recorrente'),
    path('compras_recorrentes/<int:compra_id>/marcar_realizada/', views.marcar_compra_realizada, name='marcar_compra_realizada'),
]