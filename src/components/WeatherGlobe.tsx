import React, { useMemo } from 'react';
import Globe from 'react-globe.gl';

interface WeatherGlobeProps {
  data: any;
  hasData: boolean;
  displayMode: 'temp' | 'press';
  pointIndex: number;
}

const WeatherGlobe: React.FC<WeatherGlobeProps> = ({ 
  data, 
  hasData, 
  displayMode, 
  pointIndex 
}) => {

  if (!hasData || !data) return null;

  // Logic: Filter points and Transform for Labels
  const getLabelData = useMemo(() => {
    let sourcePoints = [];

    if (data.matches && data.matches.length > 0) {
      sourcePoints = [data.matches[pointIndex]];
    }

    // Helper to safely get number values
    const getValue = (obj: any, keys: string[]) => {
      for (const k of keys) {
        if (obj[k] !== undefined && obj[k] !== null) return Number(obj[k]);
      }
      return 0; // Fallback
    };

    const displayPoints = sourcePoints.flatMap((p: any) => {
      // 1. Safely extract Temp and Pressure
      const tempVal = getValue(p, ['tmp2m', 'temperature', 'T', 't', 'tmp']);
      const pressVal = getValue(p, ['press', 'pressure', 'P', 'p', 'pres']);

      const tempStr = `${tempVal.toFixed(3)}°C`;
      const pressStr = `${pressVal.toFixed(3)} atm`;

      // 2. Create the Primary Point object
      const p1 = {
        ...p,
        lat: Number(p.lat),
        lon: Number(p.lon),
        labelName: `Match #${p.id || ''}`,
        tempStr,
        pressStr
      };

      // 3. Create the Antipode (Opposite Point)
      // Lat is inverted (-lat), Lon is +180 deg
      let antiLon = p1.lon + 180;
      if (antiLon > 180) antiLon -= 360;

      const p2 = {
        ...p,
        lat: -p1.lat,
        lon: antiLon,
        labelName: `Antipode`,
        tempStr,
        pressStr
      };

      return [p1, p2];
    });

    return displayPoints;

  }, [data, pointIndex]);

  // Logic: Select Texture
  const getGlobeImage = () => {
    return displayMode === 'temp' ? data.textures.temp : data.textures.press;
  };

  return (
    <Globe
      globeImageUrl={getGlobeImage()}
      backgroundColor="#232136"
      showAtmosphere={false}
      
      // Data
      labelsData={getLabelData}
      
      // Position
      labelLat="lat"
      labelLng="lon"
      
      // Visuals
      labelText={(d: any) => `${d.tempStr} | ${d.pressStr}`} 
      labelSize={2.}
      labelDotRadius={1.} 
      labelColor={() => '#000000'}
      labelResolution={2}
      labelAltitude={0.01}
    />
  );
};

export default WeatherGlobe;
