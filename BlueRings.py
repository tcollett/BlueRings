import scipy.ndimage as  ndimage
import pylab as plt
import numpy


#-----------------------------------------
#Some functions Blue Rings needs


def getPeak(img,x,y,boxsize=10):
    from scipy import ndimage
    img = img*1
    a=img.shape[0]/2-5
    img[:a,:]=0
    img[-a:,:]=0
    img[:,:a]=0
    img[:,-a:]=0
   
    for i in range(1):
        d = ndimage.gaussian_filter(img,1.)
        Y,X = numpy.mgrid[0:d.shape[0],0:d.shape[1]]
        Y -= Y.mean()
        X -= X.mean()
        d /= d.sum()
        x = x+int(numpy.round((d*X).sum()))
        y = y+int(numpy.round((d*Y).sum()))
    return x,y


def convolve(image,psf,doPSF=True,edgeCheck=True):
    """
    A reasonably fast convolution routine that supports re-entry with a
    pre-FFT'd PSF. Returns the convolved image and the FFT'd PSF. Code written by  M. Auger.
    """
    datadim1 = image.shape[0]
    datadim2 = image.shape[1]
    if datadim1!=datadim2:
        ddim = max(datadim1,datadim2)
        s = numpy.binary_repr(ddim-1)
        s = s[:-1]+'0' # Guarantee that padding is used
    else:
        ddim = datadim1
        s = numpy.binary_repr(ddim-1)
    if s.find('0')>0:
        size = 2**len(s)
        if edgeCheck==True and size-ddim<8:
            size*=2
        boxd = numpy.zeros((size,size))
        r = size-datadim1
        r1 = r2 = r/2
        if r%2==1:
            r1 = r/2+1
        c = size-datadim2
        c1 = c2 = c/2
        if c%2==1:
            c1 = c/2+1
        boxdslice = (slice(r1,datadim1+r1),slice(c1,datadim2+c1))
        boxd[boxdslice] = image
    else:
        boxd = image

    if doPSF:
        # Pad the PSF to the image size
        boxp = boxd*0.
        if boxd.shape[0]==psf.shape[0]:
            boxp = psf.copy()
        else:
            r = boxp.shape[0]-psf.shape[0]
            r1 = r/2+1
            c = boxp.shape[1]-psf.shape[1]
            c1 = c/2+1
            boxpslice = (slice(r1,psf.shape[0]+r1),slice(c1,psf.shape[1]+c1))
            boxp[boxpslice] = psf.copy()
        # Store the transform of the image after the first iteration
        a = (numpy.fft.rfft2(boxp))
    else:
        a = psf
        # PSF transform and multiplication
    b = a*numpy.fft.rfft2(boxd)
    # Inverse transform, including phase-shift to put image back in center;
    #   this removes the requirement to do 2x zero-padding so makes things
    #   go a bit quicker.
    b = numpy.fft.fftshift(numpy.fft.irfft2(b)).real
    # If the image was padded, remove the padding
    if s.find('0')>0:
        b = b[boxdslice]

    return b,a




#-----------------------------------------
#Now we have the actual BlueRings code


class BlueRings():
    def __init__(self,imdict,sigdict,psfdict,pixelsize=0.265,bands=['g','r','i','z'],zeropoint=30,psfmode="none"):
        """
        Code to do difference imaging of elliptical galaxies to look for blue features caused by gravitational lensing.

        Example useage:
        -----------------------------------
        imdict={'g':g_image,'r':r_image,'i':i_image,'z':z_image}
        sigdict={'g':g_sig,'r':r_sig,'i':i_sig,'z':z_sig}
        psfdict={'g':g_psf,'r':r_psf,'i':i_psf,'z':z_psf}

        BR=BlueRings(imdict,sigdict,psfdict)
        BR.residualAnalyse(): 
        grade=BR.plot() #NB plot ends with a raw_input()
        ------------------------------------

        Help: Tom Collett, thomas.collett@port.ac.uk
        """
        self.imdict=imdict
        self.sigdict=sigdict
        self.psfdict=psfdict
        self.bands=bands
        self.pixelsize=pixelsize
        self.zeropoint=zeropoint

        
        self.findCoM(bands[-1])
        
        if psfmode=="match":
            self.psfmatch()

        self.subdict,self.subsigdict=self.imagesubtract(imdict,sigdict)
        #self.plot()


    def findCoM(self,band="z"):
        B=self.imdict[self.bands[0]]
        self.x,self.y=numpy.mgrid[0:B.shape[0],0:B.shape[1]]
        self.xc=(B.shape[0]+1.)/2
        self.yc=(B.shape[1]+1.)/2

        self.com=getPeak(self.imdict[band],self.xc,self.yc)


        self.rcent=((self.x-self.com[0])**2+(self.y-self.com[1])**2)**0.5
        self.dcent=self.rcent*self.pixelsize

        #self.com=(self.xc,self.yc)

    def psfmatch(self,band="z"):
        self.imdict["g"]=convolve(self.imdict["g"],self.psfdict['z'])[0]
        self.imdict["z"]=convolve(self.imdict["z"],self.psfdict['g'])[0]


    def imagesubtract(self,imdict,sigdict,bandtosubtract='z',matchradius=5):

        R=imdict[bandtosubtract]
        mask=((self.dcent<2.7)&(self.dcent>0.5))

        subdict={}
        subsigdict={}
        for band in imdict.keys():
          if band != bandtosubtract:
            B=imdict[band]
            alpha=B[mask].sum()*1./R[mask].sum()
            
            subdict[band]=imdict[band]-alpha*R
            subsigdict[band]=(sigdict[band]**2+
                              alpha*sigdict[bandtosubtract]**2
                              )**0.5

            #print band,sigdict[band].mean(),alpha,sigdict[bandtosubtract].mean()

        return subdict,subsigdict
           

    def residualAnalyse(self,threshold=3,apperture=4,pixelscale=0.263):
        import pylab as plt

        D=self.subdict['g'].ravel()*1
        S=self.subsigdict['g'].ravel()*1

        from scipy.ndimage.filters import gaussian_filter as gf
        Df=gf(D,1)
        D[Df/S<1]=0

        import indexTricks as iT
        x,y=iT.coords(self.subdict['g'].shape)
        x-=x.mean()
        y-=y.mean()
        r=((x**2+y**2)**0.5).ravel()

        mask=r<(apperture/pixelscale)

        D[mask==False]=0

        self.Dsn=D.reshape(self.subdict['g'].shape)


        args=numpy.argsort(-D/S)
        D=numpy.take(D,args)
        S=numpy.take(S,args)

        Dsum=numpy.cumsum(D)
        Ssum=(numpy.cumsum(S**2))**0.5

        SN=(Dsum/Ssum).max()
        print SN

        if SN>threshold:return True
        else: return False
        
 
    def plot(self,input=True,save=False):
        import pylab as plt

        figprops = dict(figsize=(7.0, 3.0), dpi=128)                                           # Figure properties
        fig = plt.figure(1,**figprops)

        # Need small space between subplots to avoid deletion due to overlap...
        adjustprops = dict(\
                           left=0.1,\
                           bottom=0.1,\
                           right=0.95,\
                           top=0.95,\
                           wspace=0.04,\
                           hspace=0.08)
        fig.subplots_adjust(**adjustprops)

        # Font sizes:
        params = { 'axes.labelsize': 16,
                   'text.fontsize': 10,
                   'legend.fontsize': 8,
                   'xtick.labelsize': 10,
                   'ytick.labelsize': 10}
        plt.rcParams.update(params)

        import colorImage
        ax1=plt.subplot(131)
        color = colorImage.ColorImage()
        color.nonlin=2

        colorimage = color.createModel(self.imdict['g'],self.imdict['r'],self.imdict['i'])
        plt.imshow(colorimage,interpolation="none")
        ax1.xaxis.set_visible(False)
        ax1.yaxis.set_visible(False)

        ax2=plt.subplot(132)
        colorimage = color.colorize(self.subdict['g'],self.subdict['r'],self.subdict['i'])
        plt.imshow(colorimage,interpolation="none")
        #plt.imshow(self.Dsn,interpolation="none")
        ax2.xaxis.set_visible(False)
        ax2.yaxis.set_visible(False)

        ax3=plt.subplot(133)
        self.subdict['g'][self.subdict['g']<0]=0
        plt.imshow(self.subdict['g'],interpolation="none")
        ax3.xaxis.set_visible(False)
        ax3.yaxis.set_visible(False)

        if save!=False:
            plt.savefig("BRoutput_%s.png"%save)

        plt.draw()

        if input:return raw_input()
        else: return