import { useState } from 'react'
import './App.css'
import { Contents } from './components/Contents/Contents'
import { Viewer } from './components/Viewer/View'
import { Artifacts } from './components/Artifacts/Artifacts'
import Document from './components/Document/Document'


function App() {
  
  return (
    <>
    {/* <div style={{display:"flex", justifyContent: "space-between", width: "100vh"}}>
    <Contents />
    <Viewer />
    <Artifacts />
    </div> */}
    <Document />
    </>
  )
}

/*
  [
    {
      id: 1,
      content: "Some Content",
      sub-section: [
        {
          id: 1.1,
          content: "Some Content",
          sub-section: [
            {
              id: mandatory,
              content: "",
              sub-section: Optional
            }
          ]
        }
      
      ]
    }

  ]

*/

export default App
