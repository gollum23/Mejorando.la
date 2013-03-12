from django.db import models
from django.conf import settings
from django.utils import simplejson
from django.db.models.signals import post_save, post_delete
from django.core.urlresolvers import reverse

import requests

import image
from utils import send_mail, calculate
import time


class Curso(models.Model):
    nombre = models.TextField()
    slug = models.TextField()
    precio = models.IntegerField()
    pais = models.CharField(max_length=50)
    direccion = models.TextField()
    mapa = models.CharField(max_length=50, blank=True)
    imagen = models.ImageField(upload_to='cursos_curso')
    descripcion = models.TextField()
    info_pago = models.TextField()
    activado = models.BooleanField(default=False)
    version = models.IntegerField(default=1)
    mailchimp = models.CharField(max_length=100, blank=True)

    def __unicode__(self):
        return self.nombre

    def has_versions(self):
        return self.get_versions().count() > 1

    def get_versions(self):
        return self.cursopago_set.values('version').annotate(models.Count('id'))

    def get_stats_url(self):
        return reverse('stats.views.single', None, [self.slug])

    # media del curso
    def get_imagen(self):
        return '%s%s' % (settings.MEDIA_URL, self.imagen)

    def get_map_link(self):
        return 'https://maps.google.com/maps?q=%s, %s' % (
            self.direccion, self.pais)

    def get_map_image(self):
        return 'http://maps.googleapis.com/maps/api/staticmap?size=335x125&maptype=roadmap&markers=icon:http://mejorando.la/nuevaVenta/images/marker.png%7C' + self.mapa + '&zoom=17&sensor=false'

    # variables externas del curso
    def dias(self):
        return CursoDia.objects.filter(curso=self)

    def docentes(self):
        return CursoDocente.objects.filter(cursos=self)

    def registros(self):
        return CursoRegistro.objects.filter(curso=self)

    def fecha(self):
        dias = CursoDia.objects.filter(curso=self)

        if dias.count() > 0:
            return dias[0].fecha

        return None

    # opciones del curso
    def is_online(self):
        return self.pais.lower() == 'online'

    def transacciones(self):
        return CursoPago.objects.filter(curso=self)

    def pagados(self):
        return CursoPago.objects.filter(charged=True, curso=self)

    def no_pagados(self):
        return CursoPago.objects.filter(charged=False, curso=self)

    def registros(self):
        return CursoRegistro.objects.filter(pago__curso=self)

    def vendidos(self):
        result = CursoPago.objects.filter(
            charged=True, curso=self
        ).aggregate(models.Sum('quantity'))['quantity__sum']

        if result is None:
            result = 0
        return result

    def noregistros(self):
        return self.vendidos() - self.registros().count()

    def stripe_total(self):
        return self.stripe_pagados().count() + self.stripe_no_pagados().count()

    def stripe_pagados(self):
        return CursoPago.objects.filter(charged=True, method='card', curso=self)

    def stripe_no_pagados(self):
        return CursoPago.objects.filter(charged=False, method='card', curso=self)

    def stripe_registros(self):
        return CursoRegistro.objects.filter(pago__curso=self, pago__method='card')

    def paypal_total(self):
        return self.paypal_pagados().count() + self.paypal_no_pagados().count()

    def paypal_pagados(self):
        return CursoPago.objects.filter(charged=True, method='paypal', curso=self)

    def paypal_no_pagados(self):
        return CursoPago.objects.filter(charged=False, method='paypal', curso=self)

    def paypal_registros(self):
        return CursoRegistro.objects.filter(pago__curso=self, pago__method='paypal')


    def deposit_total(self):
        return self.deposit_pagados().count() + self.deposit_no_pagados().count()

    def deposit_pagados(self):
        return CursoPago.objects.filter(charged=True, method='deposit', curso=self)

    def deposit_no_pagados(self):
        return CursoPago.objects.filter(charged=False, method='deposit', curso=self)

    def deposit_registros(self):
        return CursoRegistro.objects.filter(pago__curso=self, pago__method='deposit')


    
    def regions(self):
        r = []

        for p in CursoRegistro.objects.filter(
                pago__curso=self,
                pago__charged=True
        ).values('pago__pais').annotate(models.Count('id')):
            r.append([p['pago__pais'], p['id__count']])
        
        return simplejson.dumps(r)

    def timeline(self):
        pagos = CursoPago.objects.filter(charged=True, curso=self)

        return simplejson.dumps([ [ f.strftime('%b/%d'), pagos.filter(fecha__year=f.year, fecha__month=f.month, fecha__day=f.day).count() ] for f in pagos.dates('fecha', 'day')])

    def save(self, *args, **kwargs):
        super(Curso, self).save(*args, **kwargs)

        return

        if not self.id and not self.imagen: return

        image.resize((666, 430), self.imagen)

class CursoDia(models.Model):
    fecha     = models.DateTimeField()
    tema      = models.CharField(max_length=500)
    temario = models.TextField()
    curso   = models.ForeignKey(Curso)

    def __unicode__(self):
        return self.tema

class CursoDocente(models.Model):
    nombre  = models.CharField(max_length=500)
    twitter = models.CharField(max_length=300)
    perfil  = models.TextField()
    imagen  = models.ImageField(upload_to='cursos_docentes')
    cursos  = models.ManyToManyField(Curso, blank=True)

    def __unicode__(self):
        return self.nombre

    def get_imagen(self):
        return '%s%s' % (settings.MEDIA_URL, self.imagen)

    def save(self, *args, **kwargs):
        super(CursoDocente, self).save(*args, **kwargs)

        if not self.id and not self.imagen: return

        image.resize((67, 67), self.imagen)

class CursoPago(models.Model):
    TIPOS = (
        ('card', 'Stripe'),
        ('paypal', 'PayPal'),
        ('deposit', 'Deposito')
    )

    nombre      = models.CharField(max_length=500)
    email       = models.EmailField()
    telefono = models.CharField(max_length=500, null=True, blank=True)
    pais     = models.CharField(max_length=100, null=True, blank=True)
    quantity = models.IntegerField()
    fecha    = models.DateTimeField(auto_now_add=True)
    curso    = models.ForeignKey(Curso)
    charged  = models.BooleanField(default=False)
    method   = models.CharField(max_length=10, choices=TIPOS)
    error      = models.CharField(max_length=200, blank=True)
    sent     = models.BooleanField(default=False)
    version  = models.IntegerField(default=1)
    ip = models.CharField(max_length=50, blank=True)
    ua = models.TextField(blank=True)

    def intentos(self):
        return CursoPago.objects.filter(email=self.email, curso=self.curso, method=self.method).count()

    def __unicode__(self):
        return '%s - %s ' % (self.nombre, self.email)

class CursoRegistro(models.Model):
    email       = models.EmailField()
    pago     = models.ForeignKey(CursoPago)

    def __unicode__(self):
        return self.email

# HOOKS
def create_pago(sender, instance, created, *args, **kwargs):
    curso = instance.curso

    if created:
        instance.version = curso.version
        instance.save()

        if instance.method == 'deposit':
            send_mail('curso_info', { 'curso': curso }, 'Informacion para realizar pago al %s de Mejorando.la INC' % curso.nombre, instance.email)

    if instance.charged and not instance.sent:
        vs = calculate(int(instance.quantity), curso.precio)

        vs['curso'] = curso
        vs['pago']  = instance

        send_mail('curso_pago', vs, 'Gracias por tu pago al %s de Mejorando.la INC' % curso.nombre, instance.email)

        instance.sent = True
        instance.save()


def create_registro(sender, instance, created, *args, **kwargs):
    if created:
        # integracion con la plataforma
        curso = instance.pago.curso

        try:
            requests.post(u'%spreregistro' % settings.PLATAFORMA_API_URL, {'slug': curso.slug, 'email': instance.email, 'passwd': settings.PLATAFORMA_API_KEY})
        except:
            pass

        if curso.mailchimp:
            payload = {
                'email_address': instance.email,
                'apikey': settings.MAILCHIMP_APIKEY,
                'update_existing': True,
                'merge_vars': {
                    'OPTINIP': instance.pago.ip,
                    'OPTIN_TIME': time.time(),
                    'PAIS': instance.pago.pais,
                    'GROUPINGS': (dict(name='Online', groups=curso.mailchimp), )
                },
                'id': settings.MAILCHIMP_LISTID,
                'email_type': 'html'
            }

            req = requests.post('http://us4.api.mailchimp.com/1.3/?method=listSubscribe', simplejson.dumps(payload))

            if not req.text == 'true':
                payload = payload = {
                    'email_address': instance.email,
                    'apikey': settings.MAILCHIMP_APIKEY,
                    'update_existing': True,
                    'merge_vars': {
                        'FNAME': instance.pago.nombre,
                        'OPTINIP': instance.pago.ip,
                        'OPTIN_TIME': time.time(),
                        'PAIS': instance.pago.pais,
                        'GROUPINGS': (dict(name='Online', groups=curso.mailchimp), )
                    },
                    'id': settings.MAILCHIMP_LISTID,
                    'email_type': 'html'
                }

                requests.post('http://us4.api.mailchimp.com/1.3/?method=listSubscribe', simplejson.dumps(payload))


def delete_registro(sender, instance, **kwargs):
    # integracion con la plataforma
    curso = instance.pago.curso

    try:
        requests.post(u'%sdelete_preregistro' % settings.PLATAFORMA_API_URL, {'slug': curso.slug, 'email': instance.email, 'passwd': settings.PLATAFORMA_API_KEY})
    except:
        pass

post_save.connect(create_pago, sender=CursoPago)
post_save.connect(create_registro, sender=CursoRegistro)
post_delete.connect(delete_registro, sender=CursoRegistro)
