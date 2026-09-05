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
    <div className="bg-[#FAF8F5] border-2 border-[#1C2B3A] p-2 rounded-none relative">
      {/* Forensic Registration Marks at Corners */}
      <div className="absolute top-1 left-1 text-[10px] font-mono text-[#1C2B3A] select-none font-bold">+</div>
      <div className="absolute top-1 right-1 text-[10px] font-mono text-[#1C2B3A] select-none font-bold">+</div>
      <div className="absolute bottom-1 left-1 text-[10px] font-mono text-[#1C2B3A] select-none font-bold">+</div>
      <div className="absolute bottom-1 right-1 text-[10px] font-mono text-[#1C2B3A] select-none font-bold">+</div>

      {/* Top Horizontal Millimeter Ruler Bar */}
      <div className="ml-7 mb-1 h-5 bg-[#FAF8F5] border-b border-[#1C2B3A] relative overflow-hidden flex items-end">
        <div className="w-full flex justify-between text-[8px] font-mono text-[#1C2B3A] px-1 select-none">
          <span>0mm</span>
          <span>20</span>
          <span>40</span>
          <span>60</span>
          <span>80</span>
          <span>100</span>
          <span>120</span>
          <span>140</span>
          <span>160</span>
          <span>180</span>
          <span>200mm</span>
        </div>
        {/* Repeating millimeter tick lines */}
        <div className="absolute bottom-0 left-0 right-0 h-1.5 flex justify-between px-1">
          {Array.from({ length: 21 }).map((_, i) => (
            <span
              key={i}
              className={`w-[1px] bg-[#1C2B3A] ${i % 2 === 0 ? 'h-2' : 'h-1'}`}
            />
          ))}
        </div>
      </div>

      <div className="flex">
        {/* Left Vertical Millimeter Ruler Bar */}
        <div className="w-6 mr-1 bg-[#FAF8F5] border-r border-[#1C2B3A] relative overflow-hidden flex flex-col justify-between text-[8px] font-mono text-[#1C2B3A] py-1 select-none shrink-0 text-right pr-1">
          <span>0</span>
          <span>30</span>
          <span>60</span>
          <span>90</span>
          <span>120</span>
          <span>150</span>
          <span>180</span>
          <span>210</span>
          <span>240mm</span>
        </div>

        {/* Specimen Viewport Container */}
        <div className="relative flex-1 bg-white border border-[#D8D2C6] flex items-center justify-center min-h-[350px] overflow-hidden">
          <img
            ref={imgRef}
            src={imageUrl}
            alt="Physical Packaging Specimen"
            onLoad={handleImageLoad}
            className="max-h-[550px] w-auto max-w-full object-contain select-none block"
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

                let strokeColor = "#2F6F4E"; // Compliant Forest Green
                let fillColor = "rgba(47, 111, 78, 0.15)";
                let badgeBg = "#2F6F4E";

                if (info.font_compliant === false || info.format_valid === false) {
                  strokeColor = "#A8342A"; // Flagged Crimson Red
                  fillColor = "rgba(168, 52, 42, 0.20)";
                  badgeBg = "#A8342A";
                } else if (info.extraction_method === 'genai_fallback') {
                  strokeColor = "#B8862B"; // Pending Amber
                  fillColor = "rgba(184, 134, 43, 0.18)";
                  badgeBg = "#B8862B";
                }

                return (
                  <g
                    key={fieldName}
                    className="pointer-events-auto cursor-pointer"
                    onClick={() => onSelectField && onSelectField(fieldName)}
                  >
                    <rect
                      x={x}
                      y={y}
                      width={w}
                      height={h}
                      fill={fillColor}
                      stroke={strokeColor}
                      strokeWidth={isSelected ? 3 : 1.5}
                      strokeDasharray={isSelected ? "4 2" : undefined}
                      rx="0"
                    />
                    <rect
                      x={x}
                      y={Math.max(0, y - 18)}
                      width={Math.max(75, fieldName.length * 8.5)}
                      height="17"
                      fill={badgeBg}
                      rx="0"
                    />
                    <text
                      x={x + 4}
                      y={Math.max(12, y - 5)}
                      fill="#FFFFFF"
                      fontSize="10"
                      fontWeight="600"
                      fontFamily="'IBM Plex Mono', monospace"
                    >
                      {fieldName}
                    </text>
                  </g>
                );
              })}
            </svg>
          )}
        </div>
      </div>

      {/* Specimen Mat Caption */}
      <div className="mt-2 pt-1 border-t border-[#D8D2C6] flex items-center justify-between text-[10px] font-mono text-[#5E6E80] px-1">
        <span>EXHIBIT A • CALIBRATED OPTICAL EVIDENCE MAP</span>
        <span>SCALE: 1.00x PHYSICAL PROJECTION</span>
      </div>
    </div>
  );
};
