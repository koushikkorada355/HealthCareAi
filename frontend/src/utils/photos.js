// Photo system: Unsplash only (no Cloudinary or other hosts).
// Every image has a gradient/initial fallback — if a remote photo fails,
// onError hides it or swaps to initials, so the UI works offline too.
const U = (id, w = 256) => `https://images.unsplash.com/${id}?auto=format&fit=crop&w=${w}&q=60`;

export const DOCTOR_PHOTOS = [
  U('photo-1559839734-2b71ea197ec2'), // female doctor, stethoscope
  U('photo-1612349317150-e413f6a5b16d'), // male doctor portrait
  U('photo-1594824476967-48c8b964273f'), // female doctor smiling
  U('photo-1622253692010-333f2da6031d'), // male doctor, dark bg
  U('photo-1537368910025-700350fe46c7'), // care team
  U('photo-1651008376811-b90baee60c1f'), // female doctor
  U('photo-1582750433449-648ed127bb54'), // male doctor, stethoscope
  U('photo-1638202993928-7267aad84c31'), // female doctor
  U('photo-1551601651-2a8555f1a136'), // surgeons in theatre
  U('photo-1579684385127-1ef15d508118'), // doctor portrait
  U('photo-1612349316228-5942a9b489c2'), // male doctor portrait
  U('photo-1580489944761-15a19d654956'), // portrait
];

export const HOSPITAL_COVERS = [
  U('photo-1519494026892-80bbd2d6fd0d', 1200), // hospital corridor
  U('photo-1586773860418-d37222d8fce3', 1200), // hospital building
  U('photo-1538108149393-fbbd81895907', 1200), // imaging suite
  U('photo-1516549655169-df83a0774514', 1200), // surgical team
  U('photo-1512678080530-7760d81faba6', 1200), // clinic hallway
  U('photo-1587854692152-cbe660dbde88', 1200), // hospital exterior
];

/* Specialty banners for the booking flow. */
export const SPECIALTY_IMAGES = {
  Orthopedics: U('photo-1516549655169-df83a0774514', 600),
  Cardiology: U('photo-1628348068343-c6a848d2b6dd', 600),
  Dermatology: U('photo-1570172619644-dfd03ed5d881', 600),
  Neurology: U('photo-1559757148-5c350d0d3c56', 600),
  Pediatrics: U('photo-1503454537195-1dcabb73ffb9', 600),
  'General Medicine': U('photo-1576091160399-112ba8d25d1d', 600),
};

export const HERO_IMG = U('photo-1576091160399-112ba8d25d1d', 1000); // doctor with tablet
export const VOICE_IMG = U('photo-1576091160550-2173dba999ef', 800); // telehealth consult
export const VOICE_SIDE = U('photo-1579684385127-1ef15d508118', 600); // doctor portrait
export const CARE_TEAM = U('photo-1631217868264-e5b90bb7e133', 800); // clinical care

export function doctorPhoto(seed, explicit) {
  if (explicit) return explicit;
  const n = Number(seed) || String(seed || 'x').length;
  return DOCTOR_PHOTOS[n % DOCTOR_PHOTOS.length];
}

export function hospitalCover(slug) {
  const s = String(slug || 'x');
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return HOSPITAL_COVERS[h % HOSPITAL_COVERS.length];
}

export function specialtyImage(spec) {
  return SPECIALTY_IMAGES[spec] || HERO_IMG;
}
