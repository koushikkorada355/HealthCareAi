import React from 'react'
import { Routes, Route } from 'react-router-dom'
import Landing from './pages/public/Landing.jsx'
import { Login, Register, Forgot, HospitalApply } from './pages/public/Auth.jsx'
import { Require } from './routes/guards.jsx'
import Home from './pages/patient/Home.jsx'
import Assistant from './pages/patient/Assistant.jsx'
import Voice from './pages/patient/Voice.jsx'
import { Hospitals, Doctors, Slots } from './pages/patient/Discovery.jsx'
import { BookFind, BookSlots } from './pages/patient/Book.jsx'
import { Upcoming, History, Detail, Questionnaires, QFill, Prefs, Profile } from './pages/patient/Appts.jsx'
import { Dash as DocDash, ApptList, Calendar, Availability, ApptDetail } from './pages/doctor/Doctor.jsx'
import { Dash as HDash, Doctors as HDocs, DoctorDetail, Schedules, Appointments as HAppts, Questionnaires as HQ, AIActivity as HAI, Integrations as HInt, Workflows as HWf, Notifications, Analytics as HAn, Audit as HAud } from './pages/hospital/Hospital.jsx'
import { Dash as ADash, Applications, ApplicationDetail, TablePage, AIActivity as AAI, Analytics as AAn, OpsHealth } from './pages/admin/Admin.jsx'

const isToday = (a) => new Date(a.starts_at).toDateString() === new Date().toDateString()
const isUpcoming = (a) => new Date(a.starts_at) >= new Date() && ['confirmed', 'pending', 'rescheduled'].includes(a.status)

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<Forgot />} />
      <Route path="/hospitals/apply" element={<HospitalApply />} />

      {/* patient */}
      <Route path="/app" element={<Require roles={['patient']}><Home /></Require>} />
      <Route path="/app/assistant" element={<Require roles={['patient']}><Assistant /></Require>} />
      <Route path="/app/voice" element={<Require roles={['patient']}><Voice /></Require>} />
      <Route path="/app/hospitals" element={<Require roles={['patient']}><Hospitals /></Require>} />
      <Route path="/app/doctors" element={<Require roles={['patient']}><Doctors /></Require>} />
      <Route path="/app/doctors/:id/slots" element={<Require roles={['patient']}><Slots /></Require>} />
      {/* creative 2-page booking flow: Page 1 find → Page 2 slots+confirm */}
      <Route path="/app/book" element={<Require roles={['patient']}><BookFind /></Require>} />
      <Route path="/app/book/:id" element={<Require roles={['patient']}><BookSlots /></Require>} />
      <Route path="/app/upcoming" element={<Require roles={['patient']}><Upcoming /></Require>} />
      <Route path="/app/history" element={<Require roles={['patient']}><History /></Require>} />
      <Route path="/app/appointments/:id" element={<Require roles={['patient']}><Detail /></Require>} />
      <Route path="/app/questionnaires" element={<Require roles={['patient']}><Questionnaires /></Require>} />
      <Route path="/app/questionnaires/:id" element={<Require roles={['patient']}><QFill /></Require>} />
      <Route path="/app/preferences" element={<Require roles={['patient']}><Prefs /></Require>} />
      <Route path="/app/profile" element={<Require roles={['patient']}><Profile /></Require>} />

      {/* doctor */}
      <Route path="/doctor" element={<Require roles={['doctor']}><DocDash /></Require>} />
      <Route path="/doctor/today" element={<Require roles={['doctor']}><ApptList title="Today's appointments" filter={isToday} /></Require>} />
      <Route path="/doctor/upcoming" element={<Require roles={['doctor']}><ApptList title="Upcoming appointments" filter={isUpcoming} /></Require>} />
      <Route path="/doctor/appointments" element={<Require roles={['doctor']}><ApptList title="All appointments" /></Require>} />
      <Route path="/doctor/appointments/:id" element={<Require roles={['doctor']}><ApptDetail /></Require>} />
      <Route path="/doctor/calendar" element={<Require roles={['doctor']}><Calendar /></Require>} />
      <Route path="/doctor/availability" element={<Require roles={['doctor']}><Availability /></Require>} />

      {/* hospital admin */}
      <Route path="/hospital" element={<Require roles={['hospital_admin']}><HDash /></Require>} />
      <Route path="/hospital/doctors" element={<Require roles={['hospital_admin']}><HDocs /></Require>} />
      <Route path="/hospital/doctors/:id" element={<Require roles={['hospital_admin']}><DoctorDetail /></Require>} />
      <Route path="/hospital/schedules" element={<Require roles={['hospital_admin']}><Schedules /></Require>} />
      <Route path="/hospital/appointments" element={<Require roles={['hospital_admin']}><HAppts /></Require>} />
      <Route path="/hospital/questionnaires" element={<Require roles={['hospital_admin']}><HQ /></Require>} />
      <Route path="/hospital/ai" element={<Require roles={['hospital_admin']}><HAI /></Require>} />
      <Route path="/hospital/integrations" element={<Require roles={['hospital_admin']}><HInt /></Require>} />
      <Route path="/hospital/workflows" element={<Require roles={['hospital_admin']}><HWf /></Require>} />
      <Route path="/hospital/notifications" element={<Require roles={['hospital_admin']}><Notifications /></Require>} />
      <Route path="/hospital/analytics" element={<Require roles={['hospital_admin']}><HAn /></Require>} />
      <Route path="/hospital/audit" element={<Require roles={['hospital_admin']}><HAud /></Require>} />

      {/* platform admin */}
      <Route path="/admin" element={<Require roles={['platform_admin']}><ADash /></Require>} />
      <Route path="/admin/applications" element={<Require roles={['platform_admin']}><Applications /></Require>} />
      <Route path="/admin/applications/:id" element={<Require roles={['platform_admin']}><ApplicationDetail /></Require>} />
      <Route path="/admin/hospitals" element={<Require roles={['platform_admin']}><TablePage title="Hospitals" path="/hospitals" cols={['id', 'name', 'status', 'city', 'ehr_vendor']} /></Require>} />
      <Route path="/admin/doctors" element={<Require roles={['platform_admin']}><TablePage title="Doctors" path="/doctors" cols={['id', 'name', 'specialty', 'hospital_name', 'status']} /></Require>} />
      <Route path="/admin/patients" element={<Require roles={['platform_admin']}><TablePage title="Patients" path="/patients" cols={['id', 'full_name', 'email', 'external_patient_id']} /></Require>} />
      <Route path="/admin/appointments" element={<Require roles={['platform_admin']}><TablePage title="Appointments" path="/appointments" cols={['id', 'status', 'starts_at', 'doctor_name', 'patient_name', 'integration_status']} /></Require>} />
      <Route path="/admin/ai" element={<Require roles={['platform_admin']}><AAI /></Require>} />
      <Route path="/admin/analytics" element={<Require roles={['platform_admin']}><AAn /></Require>} />
      <Route path="/admin/audit" element={<Require roles={['platform_admin']}><TablePage title="Audit log" path="/audit" cols={['id', 'action', 'entity', 'correlation_id']} /></Require>} />
      <Route path="/admin/ops" element={<Require roles={['platform_admin']}><OpsHealth /></Require>} />

      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}

function NotFound() {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center p-8 text-center">
      <div className="font-display text-5xl font-semibold">404</div>
      <p className="mt-2 text-sm text-ink-soft">That page does not exist or you do not have access to it.</p>
      <a href="/" className="btn-primary mt-5 text-sm">Back to home</a>
    </div>
  )
}
