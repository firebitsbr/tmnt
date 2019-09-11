#coding: utf-8
"""
Copyright (c) 2019 The MITRE Corporation.
"""


import mxnet as mx
import numpy as np
from scipy import special as sp
from mxnet import gluon
from tmnt.distributions.latent_distrib import LatentDistribution

__all__ = ['HyperSphericalLatentDistribution']

class HyperSphericalLatentDistribution(LatentDistribution):

    def __init__(self, n_latent, kappa=100.0, dr=0.2, ctx=mx.cpu()):
        super(HyperSphericalLatentDistribution, self).__init__(n_latent, ctx)
        self.ctx = ctx
        self.kappa = kappa
        self.kld_v = np.float(HyperSphericalLatentDistribution._vmf_kld(self.kappa, self.n_latent))
        self.dim = n_latent - 1
        self.b = self.dim / (np.sqrt(4. * kappa ** 2 + self.dim ** 2) + 2 * kappa)  # b= 1/(sqrt(4.* kdiv**2 + 1) + 2 * kdiv)
        self.x = (1. - self.b) / (1. + self.b)
        self.c = self.kappa * self.x + self.dim * np.log(1 - self.x ** 2)  # dim * (kdiv *x + np.log(1-x**2))
        aa = self.dim / 2.0
        self.approx_var = np.sqrt(aa * aa / ( (4 * aa * aa)  * (2 * aa + 1) ))
        self.num_samples = 100000
        self.w_samples = self._pregenerate_samples(num_samples=self.num_samples)
        with self.name_scope():
            self.kld_const = self.params.get('kld_const', shape=(1,), init=mx.init.Constant([self.kld_v]), differentiable=False)
            self.vmf_samples = self.params.get('vmf_samples', shape=(self.num_samples,), grad_req='null',
                                               init = mx.init.Constant([self.kld_v]), differentiable=False)
            self.mu_encoder = gluon.nn.Dense(units = n_latent)
            self.mu_bn = gluon.nn.BatchNorm(momentum = 0.001, epsilon=0.001)
            self.post_sample_dr_o = gluon.nn.Dropout(dr)            
        self.mu_bn.collect_params().setattr('grad_req', 'null')
        self.vmf_samples.initialize(ctx=self.ctx)
        self.vmf_samples.set_data(self.w_samples)
        

    def hybrid_forward(self, F, data, batch_size, kld_const, vmf_samples):
        mu = self.mu_encoder(data)
        mu_bn = self.mu_bn(mu)
        kld = F.broadcast_to(kld_const, shape=(batch_size,))
        z_p = self._get_hypersphere_sample(F, mu_bn, batch_size, vmf_samples)
        z = self.post_sample_dr_o(z_p)
        return F.softmax(z), kld


    """
    Method to pre-generate 
    """
    def _pregenerate_samples(self, num_samples=100000):
        dim = self.n_latent
        kappa = self.kappa
        dim = dim - 1
        b = self.b
        dim = self.dim
        x = self.x
        c = self.c
        mask = mx.nd.ones(num_samples, ctx=self.ctx)
        zeros = mx.nd.zeros(num_samples, ctx=self.ctx)
        w_f = mx.nd.zeros(num_samples, ctx=self.ctx)
        zz = mx.nd.zeros(1, ctx=self.ctx)
        while mx.nd.sum(mask) > 0.0:
            z = mx.nd.clip(mx.nd.random.normal(0.5, self.approx_var, num_samples, ctx=self.ctx), 1e-6, 1.0 - 1e-6)
            w = (1. - (1. + b) * z) / (1. - (1. - b) * z)
            u = mx.nd.random.uniform(0, 1, num_samples, ctx=self.ctx)
            accept = kappa * w + dim * mx.nd.log(1. - x * w) - c >= mx.nd.log(u)
            reject = 1 - accept
            mask = mx.nd.where(accept, zeros, mask)  # if reject = 1 then return mask as is, otherwise turn it off 
            w_f = mx.nd.where(mask, w_f, w)  # if mask is 1, then don't use w and leave as unset
        return w_f
    
    def _get_hypersphere_sample(self, F, mu, batch_size, vmf_samples):
        sw = self._get_weight_from_cache(F, batch_size, vmf_samples)
        #sw = self._get_weight_batch(F, batch_size)
        sw = F.expand_dims(sw, axis=1)
        sw_v = F.broadcast_to(sw, shape=(batch_size, self.n_latent))
        vv = self._get_orthonormal_batch(F, mu, batch_size)
        sc11 = F.ones((batch_size, self.n_latent), ctx=self.model_ctx)
        sc22 = sw_v ** 2.0
        sc_factor = F.sqrt(sc11 - sc22)
        orth_term = vv * sc_factor
        mu_scaled = mu * sw_v
        return orth_term + mu_scaled    

    @staticmethod
    def _vmf_kld(k, d):
        return np.array([(k * ((sp.iv(d / 2.0 + 1.0, k) + sp.iv(d / 2.0, k) * d / (2.0 * k)) / sp.iv(d / 2.0, k) - d / (2.0 * k))
               + d * np.log(k) / 2.0 - np.log(sp.iv(d / 2.0, k))
               - sp.loggamma(d / 2 + 1) - d * np.log(2) / 2).real])

    def _get_weight_from_cache(self, F, batch_size, vmf_samples):
        to_select = F.random.randint(low=0, high=self.num_samples, shape=(batch_size,))
        return F.take(vmf_samples, to_select)

    def _get_weight_batch(self, F, batch_size):
        dim = self.n_latent
        kappa = self.kappa
        dim = dim - 1
        b = self.b
        dim = self.dim
        x = self.x
        c = self.c
        mask = F.ones(batch_size, ctx=self.ctx)
        zeros = F.zeros(batch_size, ctx=self.ctx)
        w_f = F.zeros(batch_size, ctx=self.ctx)
        zz = F.zeros(1, ctx=self.ctx)
        while F.broadcast_greater(F.sum(mask), zz):
            z = F.clip(F.random.normal(0.5, self.approx_var, batch_size, ctx=self.ctx), 0.000001, 0.99999)
            w = (1. - (1. + b) * z) / (1. - (1. - b) * z)
            u = F.random.uniform(0, 1, batch_size, ctx=self.ctx)
            accept = kappa * w + dim * F.log(1. - x * w) - c >= F.log(u)
            reject = 1 - accept
            mask = F.where(accept, zeros, mask)  # if reject = 1 then return mask as is, otherwise turn it off 
            w_f = F.where(mask, w_f, w)  # if mask is 1, then don't use w and leave as unset 
        return w

    def _get_weight_batch_old(self, F, batch_size):
        batch_sample = F.zeros((batch_size,), ctx=self.model_ctx)
        for i in range(batch_size):
            batch_sample[i] = self._get_single_weight()
        return batch_sample

    def _get_single_weight(self):
        dim = self.n_latent
        kappa = self.kappa
        dim = dim - 1
        b = self.b
        dim = self.dim
        x = self.x
        c = self.c
        #b = dim / (np.sqrt(4. * kappa ** 2 + dim ** 2) + 2 * kappa)  # b= 1/(sqrt(4.* kdiv**2 + 1) + 2 * kdiv)
        #x = (1. - b) / (1. + b)
        #c = kappa * x + dim * np.log(1 - x ** 2)  # dim * (kdiv *x + np.log(1-x**2))

        while True:
            #z = np.random.beta(dim / 2., dim / 2.)  # concentrates towards 0.5 as d-> inf
            z = min(1.0, max(0.0,np.random.normal(0.5, self.approx_var))) ## approximation with normal for efficiency
            w = (1. - (1. + b) * z) / (1. - (1. - b) * z)
            u = np.random.uniform(low=0, high=1)
            if kappa * w + dim * np.log(1. - x * w) - c >= np.log(u):  # thresh is dim *(kdiv * (w-x) + log(1-x*w) -log(1-x**2))
                return w

    def _get_orthonormal_batch(self, F, mu, batch_size):
        mu_1       = F.expand_dims(mu, axis=1)
        rv         = F.random_normal(loc=0, scale=1, shape=(batch_size, self.n_latent, 1), ctx=self.model_ctx)
        rescaled_1 = F.squeeze(F.linalg.gemm2(mu_1, rv), axis=2)
        rescaled   = F.broadcast_to(rescaled_1, shape=(batch_size, self.n_latent))
        proj_mu_v  = F.broadcast_mul(mu, rescaled)        
        o_vec      = rv.squeeze() - proj_mu_v
        o_norm     = F.norm(o_vec, axis=1, keepdims=True)
        return F.broadcast_div(o_vec, o_norm)



