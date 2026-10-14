import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath } from 'reactflow';

export default function CableEdge({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data = {}, style = {}, markerEnd }) {
  const [path, x, y] = getSmoothStepPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, borderRadius: 18 });
  const width = data.total_cores >= 96 ? 5 : data.total_cores >= 48 ? 4 : 2.5;
  const cores = data.core_numbers?.length ? `Core ${data.core_numbers.join(', ')}` : data.total_cores ? `${data.total_cores} cores` : data.kind === 'drop' ? `Port ${data.port} · core count unrecorded` : 'Core count unrecorded';
  const color = style.stroke || '#7587a5';
  return <><path d={path} fill="none" stroke={color} strokeWidth={width + 9} opacity={0.07} />
    <BaseEdge id={id} path={path} markerEnd={markerEnd} style={{ ...style, strokeWidth: width }} />
    <EdgeLabelRenderer><div className="cable-edge-label nodrag nopan" title={`${data.cable_name || 'Fibre link'} · ${cores}`} style={{ transform: `translate(-50%, -50%) translate(${x}px,${y}px)`, opacity: style.opacity ?? 1, borderColor: color }}><strong>{data.cable_name || (data.kind === 'distribution' ? 'Distribution link' : data.kind === 'drop' ? 'Drop cable' : 'Fibre link')}</strong><span>{cores}</span></div></EdgeLabelRenderer>
  </>;
}
