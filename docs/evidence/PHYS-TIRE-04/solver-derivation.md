# 同一接触方程的牛顿导数

基线是PHYS-TIRE-03的后向Euler力-轮-车体共同积分。复用初值只改变求根路径；若继续用解析导数，仍必须求同一残差，不修改物理方程、制动投影或验收门槛。本页记录推导，实施与验收以源码/测试/轨迹为准。

对一次局部轮求解，除本轮外的车体贡献固定。令轮惯量I、半径r、子步h、对称接点逆质量m；制动反力B为原容量区间内的投影。其无约束需求对Fx/Fy的导数分别为：

`Bx=(m.xt−r/I)/(1/I+m.tt)`，`By=m.yt/(1/I+m.tt)`。

需求落在制动容量内时采用上述导数；饱和时导数为零。容量为零时B恒零。投影边界采用该分段函数的一个半光滑导数，线搜索仍检查原真实残差，没有失败后的替代受力模型。

末相对滑移`S=(rωnew−vxnew,−vynew)`对力的导数为：

```
Sx,x = −h(r²/I+m.xx) + h(m.xt−r/I)Bx
Sx,y = −h m.xy          + h(m.xt−r/I)By
Sy,x = −h m.xy          + h m.yt Bx
Sy,y = −h m.yy          + h m.yt By
```

接触区变形速率为`ż=(F−Kzold)/(Kh+b)`，路面滑移`P=S−ż`，故`dP/dF=dS/dF−Identity/(Kh+b)`。纵向末速度导数`dVx/dF=h[(m.xx,m.xy)−m.xt(Bx,By)]`。滚动分母`V=max(|vxnew|,slip_speed)`在各分段取对应导数。

滚动路面模型可用`q=(Cx Px/V,Cy Py/V)`表达，因为`alpha=atan2(−Py,V)`且V正，原`−Cy tan(alpha)`等价于`Cy Py/V`。计算残差仍使用原函数；这个等价式只用于导数。令Q=|q|、D为轮荷预算、n=Q/(shape D)、u=(1−E)n+E atan(n)，原MF幅值`phi=D sin(shape atan(u))`，则：

`phi' = cos(shape atan(u)) [(1−E)+E/(1+n²)]/(1+u²)`。

目标力对q的导数为`(phi/Q)Identity + (phi'−phi/Q) qqᵀ/Q²`；Q=0时取连续极限Identity，D=0时取零。再乘`dq/dF`并以Identity减去目标导数，即原Fx/Fy残差的Jacobian。无需以Fx±0.01N、Fy±0.01N四次重算目标来近似导数。

低速Coulomb模式的试验力`A=Kzold+(Kh+b)S`。圆内目标A，导数`(Kh+b)dS/dF`；圆外目标`D A/|A|`，导数`D/|A| (Identity−AAᵀ/|A|²)dA/dF`。这仍保留真实静止与滑动模式。D=0时目标恒零，导数零；不通过经验滑移或力钳制替代。

实施前后必须在光滑分段将解析Jacobian与独立中心差分核对，在投影边界单独验证真实残差和线搜索；随后原能量、动量、制动互补、离地/静止/倒车与整车A/B仍须通过。解析导数与初值优化的性能收益以实际调用计数和相同工况耗时衡量，不能用推导本身宣称性能或精度达标。

初轮独立差分检查为21通过、1失败：容量内静止制动工况暴露纵向滑移的制动消元项符号错误。因为`vxnew`中制动贡献为`−h m.xt B`，从`rωnew−vxnew`求导时必须加回`h m.xt dB`；现按上式修正，没有放宽导数核对门槛。初轮日志保留在`jacobian-derivative-t0.log`。
