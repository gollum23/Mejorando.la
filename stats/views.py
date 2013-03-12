# Create your views here.
from django.shortcuts import render, get_object_or_404
from cursos.models import Curso, CursoRegistro, CursoPago
from django.contrib.auth.decorators import login_required


@login_required(login_url='/admin')
def home(req):
    ctx = dict(
        cursos=Curso.objects.all()
    )

    return render(req, 'stats/home.html', ctx)


@login_required(login_url='/admin')
def single(req, curso_slug, version=None):
    curso = get_object_or_404(Curso, slug=curso_slug)
    version = version or curso.version

    pagos = curso.cursopago_set.filter(charged=True, version=version)
    registros = CursoRegistro.objects.filter(pago__curso=curso, pago__version=version)
    transac = curso.cursopago_set.filter(version=version)

    items = CursoPago.objects.raw("""
        SELECT id, nombre, email, pais, method, quantity, COUNT(1) AS intentos FROM cursos_cursopago
        WHERE cursos_cursopago.curso_id = %s AND cursos_cursopago.version = %s
        GROUP BY cursos_cursopago.email
        ORDER BY cursos_cursopago.fecha
        """, [curso.id, version])

    ctx = dict(
        curso=curso,
        cursos=Curso.objects.all(),
        version=version,
        pagos=pagos.count(),
        registros=registros.count(),
        transac=transac.count(),
        items=items
    )

    return render(req, 'stats/single.html', ctx)
