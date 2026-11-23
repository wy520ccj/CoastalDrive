"""真实候选遍历对完整旧查询逐位核对，覆盖顺序/缓存/异常与引用释放。"""

import gc
import weakref
from types import SimpleNamespace

import lab_query_reference as reference
import numpy as np
import pytest
from test_lab_surface_cache import assert_geometry, layout
from wheel_contact_kernels import radial_query_hits

from radial_geometry import RadialHit, RadialRoads, UnsprungGeometry
from vehicle_designs import REFERENCE_DESIGN

reference.RadialHit=RadialHit
reference.UnsprungGeometry=UnsprungGeometry


class Surface:
    def __init__(self,index,plane,dtype,trace):
        self.body,self.plane,self.index,self.dtype,self.trace=f'road-{index}',plane,index,dtype,trace

    def values(self,center):
        dtype=self.dtype;limit=REFERENCE_DESIGN.wheel_radius+REFERENCE_DESIGN.suspension_travel
        normal=np.array((np.sqrt(.75),0.,.5),dtype=dtype)
        rejected=normal.copy();rejected[2]=np.nextafter(dtype(.5),dtype(0.))
        point=center+np.array((-0.,.01,0.))
        distance=dtype(limit)
        return ((dtype(-.01),rejected,point,None),(distance,normal,point,None),
                (dtype(.01),normal,point,None),(dtype(.01),normal,point+1.,None))

    def query_plane(self,centers,axes,config):
        self.trace.append(('plane',self.index,centers.tobytes(),centers.strides,axes.strides))
        return tuple(self.values(center)[2] for center in centers)

    def query(self,center,axis,config):
        self.trace.append(('query',self.index,center.tobytes(),center.strides,axis.strides))
        yield from self.values(center)


def hit_bits(actual,expected):
    for first,last in zip(actual.hits,expected.hits):
        if first is None:assert last is None;continue
        for a,b in zip((*first.point,*first.normal),(*last.point,*last.normal)):
            assert type(a) is type(b) and np.asarray(a).tobytes()==np.asarray(b).tobytes()


@pytest.mark.parametrize('cached',[False,True])
@pytest.mark.parametrize('dtype',[np.float32,np.float64])
@pytest.mark.parametrize('kind',['planes','finite','mixed'])
@pytest.mark.parametrize('arrangement',['C','F','strided','reverse'])
def test_full_queries_keep_order_ties_scalar_types_layout_and_cache(cached,dtype,kind,arrangement):
    traces=[[],[]];runs=[]
    for trace in traces:
        surfaces=tuple(Surface(i,((0.,0.,1.),0.) if kind=='planes' or kind=='mixed' and i%2==0 else None,dtype,trace) for i in range(3))
        runs.append(SimpleNamespace(config=REFERENCE_DESIGN,surfaces=surfaces))
    caches=[[{} for _ in run.surfaces] if cached else None for run in runs]
    centers=layout(np.arange(12,dtype=float).reshape(4,3)*.01,arrangement)
    axes=layout(np.tile((1.,0.,0.),(4,1)),arrangement);up=np.array((0.,0.,1.))
    for tick in range(4):
        if tick==2:centers[1,0]=np.nextafter(centers[1,0],np.inf)
        a=RadialRoads.query(runs[0],centers,up,axes,surface_cache=caches[0])
        b=reference.RadialRoads.query(runs[1],centers,up,axes,surface_cache=caches[1])
        assert_geometry(a,b);hit_bits(a,b)
        assert traces[0]==traces[1]
        if cached:assert [list(c) for c in caches[0]]==[list(c) for c in caches[1]]
        assert all(hit.node=='road-0' for hit in a.hits)


@pytest.mark.parametrize('cached',[False,True])
@pytest.mark.parametrize('where',['before','after','normal','body'])
def test_original_callback_failures_keep_partial_cache_and_order(cached,where):
    traces=[[],[]];runs=[]
    class Failing(Surface):
        @property
        def body(self):
            if where=='body':raise ArithmeticError('原表面字段失败')
            return 'failure'
        @body.setter
        def body(self,value):pass
        def query(self,center,axis,config):
            self.trace.append(('failure',tuple(center)))
            if where=='before':raise ArithmeticError('原查询开始失败')
            candidate=(.001,np.array((0.,0.,1.)),center,None)
            if where=='normal':
                class Normal:
                    def __getitem__(self,index):raise ArithmeticError('原法线读取失败')
                candidate=(.001,Normal(),center,None)
            yield candidate
            if where=='after':raise ArithmeticError('原查询尾部失败')
    for trace in traces:
        runs.append(SimpleNamespace(config=REFERENCE_DESIGN,surfaces=(Surface(0,None,np.float64,trace),Failing(1,None,np.float64,trace))))
    caches=[[{},{}] if cached else None for _ in runs]
    centers=np.zeros((4,3));axes=np.tile((1.,0.,0.),(4,1));up=np.array((0.,0.,1.))
    for _ in range(2):
        errors=[]
        for index,query in enumerate((RadialRoads.query,reference.RadialRoads.query)):
            with pytest.raises(ArithmeticError) as error:query(runs[index],centers,up,axes,surface_cache=caches[index])
            errors.append(str(error.value))
        assert errors[0]==errors[1] and traces[0]==traces[1]
        if cached:assert [list(c) for c in caches[0]]==[list(c) for c in caches[1]]


@pytest.mark.parametrize('cached',[False,True])
@pytest.mark.parametrize('failure',[False,True])
def test_candidates_release_numpy_buffers_after_query_or_exception(cached,failure):
    references=[]
    class Temporary:
        body='temporary';plane=None
        def query(self,center,axis,config):
            normal,point=np.array((0.,0.,1.)),np.array((0.,0.,.1))
            references.extend((weakref.ref(normal),weakref.ref(point)))
            yield .01,normal,point,None
            if failure:raise ArithmeticError('结束前失败')
    roads=SimpleNamespace(config=REFERENCE_DESIGN,surfaces=(Temporary(),))
    centers=np.zeros((4,3));axes=np.tile((1.,0.,0.),(4,1));cache=[{}] if cached else None
    for _ in range(20):
        if failure:
            with pytest.raises(ArithmeticError):RadialRoads.query(roads,centers,np.array((0.,0.,1.)),axes,surface_cache=cache)
        else:RadialRoads.query(roads,centers,np.array((0.,0.,1.)),axes,surface_cache=cache)
        if cached:cache[0].clear()
    gc.collect()
    assert all(ref() is None for ref in references)


@pytest.mark.parametrize('problem',['objects','negative-count','outputs','shape','dtype','readonly','keys','caches'])
def test_native_traversal_buffer_and_context_errors_are_explicit(problem):
    centers=np.zeros((4,3));axes=np.tile((1.,0.,0.),(4,1));count=4
    objects=[(),(),centers,axes,None,None,REFERENCE_DESIGN,RadialHit,.5]
    outputs=[np.zeros(4),np.zeros(4),np.zeros((4,3)),np.zeros((4,3))]
    if problem=='objects':objects.pop()
    elif problem=='negative-count':count=-1
    elif problem=='outputs':outputs.pop()
    elif problem=='shape':outputs[0]=np.zeros(3)
    elif problem=='dtype':outputs[0]=outputs[0].astype(np.float32)
    elif problem=='readonly':outputs[0].flags.writeable=False
    elif problem=='keys':objects[5]=[]
    else:objects[4]=tuple(range(4));objects[5]=[{}]
    with pytest.raises((ValueError,BufferError)):radial_query_hits(tuple(objects),tuple(outputs),count)


@pytest.mark.parametrize('boundary',['distance','normal'])
def test_original_numpy_comparison_types_at_adjacent_gate_values(boundary):
    class Single:
        body='boundary';plane=None
        def query(self,center,axis,config):yield self.value
    centers=np.zeros((4,3));axes=np.tile((1.,0.,0.),(4,1));up=np.array((0.,0.,1.))
    surface=Single();roads=SimpleNamespace(config=REFERENCE_DESIGN,surfaces=(surface,))
    limit=REFERENCE_DESIGN.wheel_radius+REFERENCE_DESIGN.suspension_travel
    for dtype in (np.float32,np.float64):
        for ulps in (-2,-1,0,1,2):
            value=dtype(limit if boundary=='distance' else .5)
            for _ in range(abs(ulps)):value=np.nextafter(value,dtype(-np.inf if ulps<0 else np.inf))
            normal=np.array((np.sqrt(.75),0.,.5),dtype=dtype)
            if boundary=='normal':normal[2]=value
            surface.value=(value if boundary=='distance' else dtype(.01),normal,np.array((-0.,0.,.1)),None)
            a=RadialRoads.query(roads,centers,up,axes)
            b=reference.RadialRoads.query(roads,centers,up,axes)
            assert_geometry(a,b);hit_bits(a,b)
