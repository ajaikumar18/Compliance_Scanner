import { useState, useRef, useEffect } from 'react';
import type { FieldExtraction } from '../types';

interface BoundingBoxCanvasProps {
  imageUrl: string;
  fields: Record<string, FieldExtraction>;
  selectedField?: string | null;
  onSelectField?: (fieldName: string) => void;
}

export const BoundingBoxCanvas = ({
  imageUrl,
  fields,
  selectedField,
  onSelectField,
}: BoundingBoxCanvasProps) => {
  const imgRef = useRef<HTMLImageElement>(null);
  const [imageSize, setImageSize] = useState<{ width: number; height: number; naturalWidth: number; naturalHeight: number }>({
    width: 0,
    height: 0,
    naturalWidth: 1,
    naturalHeight: 1,
  });

  const handleImageLoad = () => {
    if (imgRef.current) {
      setImageSize({
        width: imgRef.current.clientWidth,
        height: imgRef.current.clientHeight,
        naturalWidth: imgRef.current.naturalWidth || 600,
        naturalHeight: imgRef.current.naturalHeight || 800,
      });
    }
  };

  useEffect(() => {
    const handleResize = () => {
      if (imgRef.current) {
        setImageSize(prev => ({
          ...prev,
          width: imgRef.current?.clientWidth || prev.width,
          height: imgRef.current?.clientHeight || prev.height,
        }));
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <div className="relative w-full overflow-hidden rounded-xl bg-slate-950/80 border border-slate-800 shadow-2xl flex items-center justify-center min-h-[350px]">
      <img
        ref={imgRef}
        src={imageUrl}
        alt="Product Label"
        onLoad={handleImageLoad}
        className="max-h-[600px] w-auto max-w-full object-contain select-none block"
      />

      {/* SVG Overlay for Bounding Boxes */}
      {imageSize.width > 0 && (
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none"
          style={{ width: imageSize.width, height: imageSize.height, left: '50%', transform: 'translateX(-50%)' }}
          viewBox={`0 0 ${imageSize.naturalWidth} ${imageSize.naturalHeight}`}
          preserveAspectRatio="xMidYMid meet"
        >
          {fields && Object.entries(fields).map(([fieldName, info]) => {
            if (!info || !info.bbox || !Array.isArray(info.bbox) || info.bbox.length < 4) return null;

            const [x, y, w, h] = info.bbox;
            const isSelected = selectedField === fieldName;

            let strokeColor = "#10b981"; // Emerald green (Compliant)
            let fillColor = "rgba(16, 185, 129, 0.15)";
            let badgeBg = "#047857";

            if (info.font_compliant === false || info.format_valid === false) {
              strokeColor = "#ef4444"; // Red (Violation)
              fillColor = "rgba(239, 68, 68, 0.25)";
              badgeBg = "#b91c1c";
            } else if (info.extraction_method === 'genai_fallback') {
              strokeColor = "#f59e0b"; // Amber (GenAI Fallback)
              fillColor = "rgba(245, 158, 11, 0.2)";
              badgeBg = "#b45309";
            }

            return (
              <g
                key={fieldName}
                className="pointer-events-auto cursor-pointer transition-all duration-200"
                onClick={() => onSelectField && onSelectField(fieldName)}
              >
                <rect
                  x={x}
                  y={y}
                  width={w}
                  height={h}
                  fill={fillColor}
                  stroke={strokeColor}
                  strokeWidth={isSelected ? 4 : 2}
                  strokeDasharray={isSelected ? "4" : undefined}
                  rx="3"
                  className="transition-all duration-150 hover:fill-opacity-40"
                />
                <rect
                  x={x}
                  y={Math.max(0, y - 22)}
                  width={Math.max(80, fieldName.length * 9)}
                  height="20"
                  fill={badgeBg}
                  rx="3"
                />
                <text
                  x={x + 5}
                  y={Math.max(14, y - 7)}
                  fill="#ffffff"
                  fontSize="12"
                  fontWeight="bold"
                  fontFamily="sans-serif"
                >
                  {fieldName}
                </text>
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
};
