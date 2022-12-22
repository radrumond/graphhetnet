#code adapted from https://github.com/radrumond/timehetnet

import tensorflow as tf
from tensorflow.keras.layers import Conv1D, Flatten, Dense, Input, BatchNormalization, GlobalAveragePooling1D
from tensorflow.keras.activations import softmax, relu
#from models.chameleon import *
import os
import numpy as np
import time
from MoHetNet.gnn import GraphConvLayer
from tensorflow.keras.regularizers import L2

tf.keras.backend.set_floatx('float32')

class TimeHetNet(tf.keras.Model):

    def __init__(self,
                dims_inf = [32,32,32],
                dims_pred = [32,32,32],
                activation = "relu",
                time=100,
                target_time=100,
                batchnorm = False,
                dilate    = False,
                block = ["conv"],
                dropout = 0.0,
                joint_axis=3,
                share_weights=True,
                l2_rate = 0.0):
        
        super(TimeHetNet, self).__init__()
        self.enc_type  = "None"

        self.share_weights = share_weights
        self.dropout = dropout
        self.dims_pred = dims_pred
        if len(block) == 1:
            block = f"{block},{block},{block},{block}"

        self.block = block
        self.time = time
        self.target_time = target_time
        
        self.joint_axis = joint_axis
        self.l2_rate = l2_rate

        # # Prediction network
        uf_comb = getTimeBlock(block=block[-1], dims=dims_inf, input_shape=(time,2*dims_inf[-1]+2),activation=activation,final=False,last=False, kernel_regularizer=l2_rate)
        uf_emb  = getTimeBlock(block=block[-1], dims=dims_inf, input_shape=(time,dims_inf[-1]+1),activation=activation,final=False,last=False, kernel_regularizer=l2_rate)
        self.time_ufz1  = GraphConvLayer(node_axis=self.joint_axis,
                                       combination_type = "concat",
                                       combination_net = uf_comb,
                                       prepare_net = uf_emb)

        uf_comb = getTimeBlock(block=block[-1], dims=dims_inf, input_shape=(time,2*dims_inf[-1]+2),activation=activation,final=False,last=False, kernel_regularizer=l2_rate)

        uf_emb  = getTimeBlock(block=block[-1], dims=dims_inf, input_shape=(time,dims_inf[-1]+1),activation=activation,final=False,last=False, kernel_regularizer=l2_rate)
        self.time_ufz2  = GraphConvLayer(node_axis=self.joint_axis,
                                       combination_type = "concat",
                                       combination_net = uf_comb,
                                       prepare_net = uf_emb)

        self.time_gz = getTimeBlock(block=block[-1],dims=dims_pred,activation=activation,final=False,last=True,name="pred_time_gz",input_shape=(time,dims_pred[-1]),batchnorm=batchnorm, dilate=dilate, kernel_regularizer=l2_rate)


        # # Support and Query network (start with both same weights)
        self.time_fv  = getTimeBlock(block=block[2],dims=dims_inf,activation=activation,final=False,name="s_time_fv",input_shape=(time,dims_inf[-1]+1),batchnorm=batchnorm, dilate=dilate, kernel_regularizer=l2_rate)
        self.time_gv  = getTimeBlock(block=block[2],dims=dims_inf,activation=activation,final=False,name="s_time_gv",input_shape=(time,dims_inf[-1]),batchnorm=batchnorm, dilate=dilate, kernel_regularizer=l2_rate)
        self.time_fvy = getTimeBlock(block=block[2],dims=dims_inf,activation=activation,final=False,name="s_time_fvy",input_shape=(target_time,dims_inf[-1]+1),batchnorm=batchnorm, dilate=dilate, kernel_regularizer=l2_rate)
        self.time_gvy = getTimeBlock(block=block[2],dims=dims_inf,activation=activation,final=False,name="s_time_gvy",input_shape=(target_time,dims_inf[-1]),batchnorm=batchnorm, dilate=dilate, kernel_regularizer=l2_rate)
        
        self.dense_fv = getSequential(dims=dims_inf,activation=activation,final=True,name="s_dense_fv", kernel_regularizer=l2_rate)


        # Xs
        uf_comb = getTimeBlock(block=block[1], dims=dims_inf, input_shape=(time,2*dims_inf[-1]+2),activation=activation,final=False,last=False, kernel_regularizer=l2_rate)
        uf_emb  = getTimeBlock(block=block[1], dims=dims_inf, input_shape=(time,dims_inf[-1]+1),activation=activation,final=False,last=False, kernel_regularizer=l2_rate)
        self.time_uf1  = GraphConvLayer(node_axis=self.joint_axis,
                                       combination_type = "concat",
                                       combination_net = uf_comb,
                                       prepare_net = uf_emb)

        uf_comb = getTimeBlock(block=block[1], dims=dims_inf, input_shape=(time,2*dims_inf[-1]+2),activation=activation,final=False,last=False, kernel_regularizer=l2_rate)
        uf_emb  = getTimeBlock(block=block[1], dims=dims_inf, input_shape=(time,dims_inf[-1]+1),activation=activation,final=False,last=False, kernel_regularizer=l2_rate)
        self.time_uf2  = GraphConvLayer(node_axis=self.joint_axis,
                                       combination_type = "concat",
                                       combination_net = uf_comb,
                                       prepare_net = uf_emb)
        # Ys
        if not self.share_weights:
            uf_comb = getTimeBlock(block=block[1], dims=dims_inf, input_shape=(target_time,2*dims_inf[-1]+2),activation=activation,final=False,last=False, kernel_regularizer=l2_rate)
            uf_emb  = getTimeBlock(block=block[1], dims=dims_inf, input_shape=(target_time,dims_inf[-1]+1),activation=activation,final=False,last=False, kernel_regularizer=l2_rate)
            self.time_ufy1  = GraphConvLayer(node_axis=self.joint_axis,
                                           combination_type = "concat",
                                           combination_net = uf_comb,
                                           prepare_net = uf_emb)

            uf_comb = getTimeBlock(block=block[1], dims=dims_inf, input_shape=(target_time,2*dims_inf[-1]+2),activation=activation,final=False,last=False, kernel_regularizer=l2_rate)
            uf_emb  = getTimeBlock(block=block[1], dims=dims_inf, input_shape=(target_time,dims_inf[-1]+1),activation=activation,final=False,last=False, kernel_regularizer=l2_rate)
            self.time_ufy2  = GraphConvLayer(node_axis=self.joint_axis,
                                           combination_type = "concat",
                                           combination_net = uf_comb,
                                           prepare_net = uf_emb)

        self.time_ug = getTimeBlock(block=block[1],dims=dims_inf,activation=activation,final=False,name="ux_time_g",input_shape=(time+target_time,dims_inf[-1]),batchnorm=batchnorm, dilate=dilate, kernel_regularizer=l2_rate)

        # # Vbar network
        self.time_v  = getTimeBlock(block=block[0],dims=dims_inf,activation=activation,final=False,name="vb_time_v",input_shape=(time,1),batchnorm=batchnorm, dilate=dilate, kernel_regularizer=l2_rate)
        self.time_c  = getTimeBlock(block=block[0],dims=dims_inf,activation=activation,final=False,name="vb_time_c", input_shape=(time,dims_inf[-1]),batchnorm=batchnorm, dilate=dilate, kernel_regularizer=l2_rate)

        self.time_vy  = getTimeBlock(block=block[0],dims=dims_inf,activation=activation,final=False,name="vb_time_vy",input_shape=(target_time,1),batchnorm=batchnorm, dilate=dilate, kernel_regularizer=l2_rate)
        self.time_cy  = getTimeBlock(block=block[0],dims=dims_inf,activation=activation,final=False,name="vb_time_cy", input_shape=(target_time,dims_inf[-1]),batchnorm=batchnorm, dilate=dilate, kernel_regularizer=l2_rate)

        self.drop_layer1=tf.keras.layers.Dropout(self.dropout)
        self.drop_layer2=tf.keras.layers.Dropout(self.dropout)
        self.drop_layer3=tf.keras.layers.Dropout(self.dropout)

    # input should be [Metabatch x samples X Time X features] and [Metabatch samples X labels] -- MB X samples X TargetTime X features
    def call(self, inp, training=False):
        que_x, sup_x, sup_y, edges = inp

        if len(tf.shape(edges))==3:
            edges = edges[0]

        M = tf.shape(sup_x)[0] # Metabatch
        N = tf.shape(sup_x)[1] # Batch
        T = tf.shape(sup_x)[2] # Time
        F = tf.shape(sup_x)[3] # Channels/Features

        T_hat = tf.shape(sup_y)[2] # Time
        Nq = tf.shape(que_x)[1] # Batch

        
        ##### Vbar network #####

        # Encode sup_x MxNxTxF to MxFxTxK (DS over Instances)
        vs_bar = tf.transpose(sup_x,[0,1,3,2])  # MxNxFxT
        vs_bar = tf.expand_dims(vs_bar,-1)      # MxNxFxTx1
        vs_bar = self.time_v(vs_bar,training)   # MxNxFxTxK

        vs_bar = tf.reduce_mean(vs_bar, axis=1) # MxFxTxK
        vs_bar = self.time_c(vs_bar,training) # MxFxTxK
        vs_bar = tf.transpose(vs_bar,[0,2,1,3]) # MxTxFxK

        # Encode sup_y MxNx1 to Mx1xK  # M N Th F
        cs_bar = tf.transpose(sup_y,[0,1,3,2])  # MxNxFxTh
        cs_bar = tf.expand_dims(cs_bar,-1)      # MxNxFxThx1
        cs_bar = self.time_vy(cs_bar,training)  # MxNxFxThxK

        cs_bar = tf.reduce_mean(cs_bar, axis=1) # MxFxThxK
        cs_bar = self.time_cy(cs_bar,training)   # MxFxThxK
        cs_bar = tf.transpose(cs_bar,[0,2,1,3]) # MxThxFxK
        

        ##### U network #####  (DS over Channels)
        vs_bar  = tf.tile(tf.expand_dims(vs_bar,axis=1),[1,N,1,1,1]) # MxNxTxFxK

        cs_bar  = tf.tile(tf.expand_dims(cs_bar,axis=1),[1,N,1,1,1]) # MxNxThxFxK

        sup_x_1 = tf.expand_dims(sup_x,axis=-1) # MxNxTxFx1
        u_xs = tf.concat([sup_x_1,vs_bar],-1) # MxNxTxFx(K+1)
        u_xs = tf.transpose(u_xs,[0,1,3,2,4]) # MxNxFxTx(K+1)

        sup_y_1 = tf.expand_dims(sup_y,axis=-1) # MxNxThxFx1
        u_ys = tf.concat([sup_y_1,cs_bar],-1) # MxNxThxFx(K+1)
        u_ys = tf.transpose(u_ys,[0,1,3,2,4]) # MxNxFxThx(K+1)

        # Graph time
        u_xs = self.time_uf1(u_xs, edges) # MxNxFxTxK
        u_xs = self.time_uf2(u_xs, edges) # MxNxFxTxK

        if self.share_weights:
            u_ys = self.time_uf1(u_ys, edges) # MxNxFxTxK
            u_ys = self.time_uf2(u_ys, edges) # MxNxFxTxK
        else:
            u_ys = self.time_ufy1(u_ys, edges) # MxNxFxTxK
            u_ys = self.time_ufy2(u_ys, edges) # MxNxFxTxK

        u_s = tf.concat([u_xs,u_ys],axis=3) # MxNxFxT+ThxK

        u_s = self.time_ug(u_s,training)    # MxNxFxT+ThxK  


        #### Inference Network #### (DS over Instances)
        in_xs = tf.slice(u_s,[0,0,0,0,0],[-1,-1,-1,self.time,-1]) # MxNxFxTxK  
        in_xs = tf.concat([tf.transpose(sup_x_1,[0,1,3,2,4]),in_xs],-1) # MxNxFxTx(K+1)

        in_ys = tf.slice(u_s,[0,0,0,self.time,0],[-1,-1,-1,self.target_time,-1]) # MxNxFxThxK  
        in_ys = tf.concat([tf.transpose(sup_y_1,[0,1,3,2,4]),in_ys],-1) # MxNxFxThx(K+1)

        in_xs = self.time_fv(in_xs,training) # MxNxFxTxK
        in_xs = tf.reduce_mean(in_xs, axis=1) # MxFxTxK
        in_xs = self.time_gv(in_xs,training)     # MxFxTxK
        in_xs = tf.transpose(in_xs,[0,2,1,3]) # MxTxFxK

        in_ys = self.time_fvy(in_ys,training) # MxNxFxThxK
        in_ys = tf.reduce_mean(in_ys, axis=1) # MxFxThxK
        in_ys = self.time_gvy(in_ys,training)     # MxFxThxK
        in_ys = tf.transpose(in_ys,[0,2,1,3]) # MxThxFxK


        #### Prediction Network ####
        p_xs = tf.tile(tf.expand_dims(in_xs, axis=1),[1,Nq,1,1,1]) # MxNxTxFxK
        p_ys = tf.tile(tf.expand_dims(in_ys, axis=1),[1,Nq,1,1,1]) # MxNxThxFxK
        que_x_1 = tf.expand_dims(que_x, axis=-1) # MxNxTxFx1

        in_xs = self.drop_layer1(in_xs,training=training)
        in_ys = self.drop_layer2(in_ys,training=training) 
        
        z = tf.concat([p_xs,que_x_1],axis=-1) # MxNxTxFx(K+1)
        z = tf.transpose(z,[0,1,3,2,4]) # MxNxFxTx(K+1)

        #z = self.time_fz(z,training) # MxNxFxTxK

        z = self.time_ufz1(z, edges) # MxNxFxTxK
        z = self.time_ufz2(z, edges) # MxNxFxTxK

        z = tf.transpose(z,[2,0,1,3,4])  # FxMxNxTxK
        z = self.drop_layer3(z,training=training) 

        t,f1,f2,f3 = self.time_gz(z)  
        t = tf.expand_dims(t,axis=3) # FxMxNx1xK
        out = t # FxMxNx1xK


        # loop to output target_time frames
        for _ in range(self.target_time-1):
            t,f1,f2,f3 = self.time_gz(t,initial_state=[f1,f2,f3])
            t = tf.expand_dims(t,axis=3)

            out = tf.concat([out,t],axis=3) # F M N Th K

        out = tf.concat([out, tf.transpose(p_ys,[3,0,1,2,4])],axis=-1) # F M N Th 2K 
        out = tf.transpose(tf.squeeze(self.dense_fv(out),-1),[1,2,3,0]) # M N Th F 2K

        return out

#wrapper for convolution or gru bluck
def getTimeBlock(block = "conv", dims=[32,32,1],input_shape=None,activation=None,name=None,final=True,batchnorm=False,dilate=False,last=False, kernel_regularizer = None):

    if block == "conv":

        return convBlock(dims=dims,input_shape=input_shape,activation=activation,name=name,final=final,batchnorm=batchnorm,dilate=dilate, kernel_regularizer= kernel_regularizer)

    elif block == "gru":

        return gruBlock(dims=dims,input_shape=input_shape,activation=activation,name=name,final=final,last=last, kernel_regularizer= kernel_regularizer)

    else:
        raise ValueError(f"Block type {block} not defined.")


#convolution block
class convBlock(tf.keras.Model):

    def __init__(self,dims=[32,32,1],input_shape=None,activation=None,name=None,final=True,batchnorm=False,dilate=False, kernel_regularizer=None):
        
        super(convBlock, self).__init__()

        self.batchnorm = batchnorm
        self.final = final
        dilation = [1,1,1]
        if dilate:
            dilation = [1,2,3]
        self.c1 = tf.keras.layers.Conv1D(filters=dims[0],kernel_size=3, activation=None,name=f"{name}-0",padding="same",dilation_rate=dilation[0],input_shape=input_shape, kernel_regularizer = L2(kernel_regularizer))
        self.relu1 = tf.keras.layers.Activation(activation)

        self.c2 = tf.keras.layers.Conv1D(filters=dims[1],kernel_size=3, activation=None,name=f"{name}-1",padding="same",dilation_rate=dilation[1],input_shape=(input_shape[0],dims[0]), kernel_regularizer = L2(kernel_regularizer))
        self.relu2 = tf.keras.layers.Activation(activation)

        if self.final:
            self.c3 = tf.keras.layers.Conv1D(filters=1,kernel_size=3, activation=None,name=f"{name}-2",padding="same",dilation_rate=dilation[2],input_shape=(input_shape[0],dims[1]), kernel_regularizer = L2(kernel_regularizer))  
        else:
            self.c3 = tf.keras.layers.Conv1D(filters=dims[2],kernel_size=3, activation=None,name=f"{name}-2",padding="same",dilation_rate=dilation[2],input_shape=(input_shape[0],dims[1]), kernel_regularizer = L2(kernel_regularizer))  

        if not self.final:
            self.relu3 = tf.keras.layers.Activation(activation) 

        if self.batchnorm:
            self.bn1 = tf.keras.layers.BatchNormalization()
            self.bn2 = tf.keras.layers.BatchNormalization()
            self.bn3 = tf.keras.layers.BatchNormalization()                 
        

    def call(self, inp, training=False):
        
        out = self.c1(inp)
        if self.batchnorm:
            out = self.bn1(out,training)
        out = self.relu1(out)

        out = self.c2(out)
        if self.batchnorm:
            out = self.bn2(out,training)
        out = self.relu2(out)

        out = self.c3(out)
        if self.batchnorm:
            out = self.bn3(out,training)
        if not self.final:
            out = self.relu3(out)

        return out

#gru block
class gruBlock(tf.keras.Model):

    def __init__(self,dims=[32,32,1],input_shape=None,activation=None,name=None,final=False,last=False, kernel_regularizer = None):
        
        super(gruBlock, self).__init__()

        self.final = final
        self.last = last

        self.g1 = tf.keras.layers.GRU(units=dims[0], return_sequences=True, return_state=True,name=f"{name}-0",input_shape=input_shape,kernel_regularizer=L2(kernel_regularizer))
        self.g2 = tf.keras.layers.GRU(units=dims[1], return_sequences=True, return_state=True,name=f"{name}-1",input_shape=input_shape,kernel_regularizer=L2(kernel_regularizer))

        if self.final:
            self.g3 = tf.keras.layers.GRU(units=1, return_sequences=True, return_state=True,name=f"{name}-3",input_shape=input_shape,kernel_regularizer=L2(kernel_regularizer))   
        else:
            self.g3 = tf.keras.layers.GRU(units=dims[2], return_sequences=True, return_state=True,name=f"{name}-3",input_shape=input_shape,kernel_regularizer=L2(kernel_regularizer))              

    def call(self, inp, training=False, initial_state=[None,None,None]):
        #input is TASKS x SAMPLES x TIME X FEATURES
        shape = tf.shape(inp)
        x = tf.reshape(inp,[-1,shape[-2],shape[-1]])
        
        x,f1 = self.g1(x,initial_state=initial_state[0])
        x,f2 = self.g2(x,initial_state=initial_state[1])
        x,f3 = self.g3(x,initial_state=initial_state[2])
        
        if self.last:
            new_shape = tf.concat([shape[:-2],[-1]],0)
            out = tf.reshape(f3,new_shape)

            return out,f1,f2,f3

        else:
            new_shape = tf.concat([shape[:-1],[-1]],0)
            out = tf.reshape(x,new_shape)

        return out

#wrapper for feed foward layers
def getSequential(dims=[32,32,1],name=None,activation=None,final=True, kernel_regularizer= None):

    final_list = []

    for idx,n in enumerate(dims):
        if final and idx == len(dims)-1:
            final_list.append(Dense(1, activation=None,name=f"{name}-{idx}",kernel_regularizer=L2(kernel_regularizer)))
        else:
            final_list.append(Dense(n, activation=activation,name=f"{name}-{idx}",kernel_regularizer=L2(kernel_regularizer)))

    return tf.keras.Sequential(final_list, name=name)