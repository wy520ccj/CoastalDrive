"""A sky that follows the car without entering the driving world."""

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    Shader,
)


def make_sky(base, _parent):

    # A camera-relative card stays behind the finite roads and fills the horizon

    # even when a different Panda3D bin is selected by the active render pipe.

    width, distance, height = 3200, 1180, 1800

    data = GeomVertexData("sky", GeomVertexFormat.getV3c4(), Geom.UHStatic)

    vertex = GeomVertexWriter(data, "vertex")

    color_writer = GeomVertexWriter(data, "color")

    colors = (
        (0.92, 0.60, 0.43, 1),
        (0.98, 0.72, 0.52, 1),
        (0.70, 0.82, 0.82, 1),
        (0.44, 0.72, 0.84, 1),
        (0.24, 0.50, 0.74, 1),
    )

    rows = len(colors)

    for row, color in enumerate(colors):
        z = -height / 2 + height * row / (rows - 1)

        for x in (-width / 2, width / 2):
            vertex.addData3f(x, distance, z)

            color_writer.addData4f(*color)

    triangles = GeomTriangles(Geom.UHStatic)

    for row in range(rows - 1):
        bottom = row * 2

        top = bottom + 2

        triangles.addVertices(bottom, bottom + 1, top + 1)

        triangles.addVertices(bottom, top + 1, top)

    geometry = Geom(data)

    geometry.addPrimitive(triangles)

    node = GeomNode("sky-dome")

    node.addGeom(geometry)

    sky = base.camera.attachNewNode(node)

    sky.setTwoSided(True)

    sky.setDepthWrite(False)

    sky.setLightOff(1)

    sky.setFogOff(1)

    sky.setShaderOff(1)

    sky.setShader(Shader.make(Shader.SL_GLSL, SKY_VERTEX, SKY_FRAGMENT), 10)

    return sky


# 云层只参与天空着色，三维道路与地形仍由场景几何遮挡。

SKY_VERTEX = """#version 130

uniform mat4 p3d_ModelViewProjectionMatrix;

in vec4 p3d_Vertex;

out vec2 skyuv;

void main(){ gl_Position=p3d_ModelViewProjectionMatrix*p3d_Vertex;

skyuv=vec2(p3d_Vertex.x/3200.+.5,p3d_Vertex.z/1800.+.5); }

"""

SKY_FRAGMENT = """#version 130

in vec2 skyuv;

out vec4 fragColor;

float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}

float noise(vec2 p){vec2 i=floor(p),f=fract(p); f=f*f*(3.-2.*f);

return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y);}

float fbm(vec2 p){float a=.5,v=0.;for(int i=0;i<5;i++){v+=a*noise(p);p=p*2.04+vec2(17.3,9.2);a*=.5;}return v;}

void main(){

 vec2 uv=skyuv;

 float y=clamp((uv.y-.62)*6.0,0.,1.);

 vec3 sky=mix(vec3(1.,.72,.39),vec3(.16,.52,.81),smoothstep(0.,1.,y));

 float sun=length((uv-vec2(.68,.70))*vec2(1.78,1.));

 sky+=vec3(.35,.18,.02)*exp(-sun*30.);

 sky=mix(sky,vec3(1.,.98,.72),1.-smoothstep(.010,.013,sun));

 vec2 p=uv*vec2(33.,49.);

 float density=fbm(p+vec2(fbm(p*.35)*2.,0.));

 float band=smoothstep(.59,.65,uv.y)*(1.-smoothstep(.82,.94,uv.y));

 float cloud=smoothstep(.48,.62,density)*band;

 float light=smoothstep(.45,.65,fbm(p+vec2(0.,.3)));

 vec3 cloudcolor=mix(vec3(.61,.57,.61),vec3(1.,.83,.54),light);

 cloudcolor=mix(cloudcolor,vec3(1.,.90,.66),smoothstep(.59,.64,density));

 sky=mix(sky,cloudcolor,cloud);

 fragColor=vec4(sky*sky,1.);

}

"""
