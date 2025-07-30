import React, { useState, useRef, useEffect } from 'react';
import { Bold, Italic, Underline, AlignLeft, AlignCenter, AlignRight, List, ListOrdered, Palette, Type, Link } from 'lucide-react';

const RichTextEditor = () => {
  const [content, setContent] = useState('');
  const [rtfData, setRtfData] = useState(null);
  const editorRef = useRef(null);

  // Initialize editor with empty content
  useEffect(() => {
    if (editorRef.current) {
      editorRef.current.innerHTML = '<p><br></p>';
    }
  }, []);

  // Convert HTML to RTF data structure compatible with Word XML
  const convertToRtfData = (htmlContent) => {
    const parser = new DOMParser();
    const doc = parser.parseFromString(htmlContent, 'text/html');
    const body = doc.body;

    const rtfStructure = {
      type: 'document',
      content: [],
      metadata: {
        created: new Date().toISOString(),
        format: 'rtf-word-compatible'
      }
    };

    const processNode = (node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        const text = node.textContent;
        if (text.trim()) {
          return {
            type: 'text',
            content: text,
            formatting: getInheritedFormatting(node.parentElement)
          };
        }
        return null;
      }

      if (node.nodeType === Node.ELEMENT_NODE) {
        const tagName = node.tagName.toLowerCase();
        const children = Array.from(node.childNodes)
          .map(processNode)
          .filter(child => child !== null);

        switch (tagName) {
          case 'p':
            return {
              type: 'paragraph',
              content: children,
              formatting: {
                alignment: getAlignment(node),
                spacing: {
                  before: 0,
                  after: 6,
                  lineSpacing: 1.15
                }
              }
            };
          
          case 'h1':
          case 'h2':
          case 'h3':
          case 'h4':
          case 'h5':
          case 'h6':
            const level = parseInt(tagName.charAt(1));
            return {
              type: 'heading',
              level: level,
              content: children,
              formatting: {
                fontSize: 20 - (level * 2),
                bold: true,
                color: '#000000',
                spacing: {
                  before: 12,
                  after: 6,
                  lineSpacing: 1.15
                }
              }
            };
          
          case 'ul':
            return {
              type: 'list',
              listType: 'bullet',
              content: children,
              formatting: {
                indent: 720, // 720 twips = 0.5 inch
                bulletStyle: 'bullet'
              }
            };
          
          case 'ol':
            return {
              type: 'list',
              listType: 'number',
              content: children,
              formatting: {
                indent: 720,
                numberStyle: 'decimal'
              }
            };
          
          case 'li':
            return {
              type: 'listItem',
              content: children,
              formatting: {
                spacing: {
                  before: 0,
                  after: 0,
                  lineSpacing: 1.15
                }
              }
            };
          
          case 'a':
            return {
              type: 'hyperlink',
              url: node.getAttribute('href') || '',
              content: children,
              formatting: {
                color: '#0066cc',
                underline: true
              }
            };
          
          case 'br':
            return {
              type: 'lineBreak'
            };
          
          default:
            if (children.length > 0) {
              return {
                type: 'span',
                content: children,
                formatting: getElementFormatting(node)
              };
            }
            return null;
        }
      }
      return null;
    };

    const processedContent = Array.from(body.childNodes)
      .map(processNode)
      .filter(item => item !== null);

    rtfStructure.content = processedContent;
    return rtfStructure;
  };

  // Get formatting from element styles and attributes
  const getElementFormatting = (element) => {
    const style = window.getComputedStyle(element);
    const formatting = {};

    // Font formatting
    if (style.fontWeight === 'bold' || style.fontWeight >= '600') {
      formatting.bold = true;
    }
    if (style.fontStyle === 'italic') {
      formatting.italic = true;
    }
    if (style.textDecoration.includes('underline')) {
      formatting.underline = true;
    }
    if (style.fontSize) {
      formatting.fontSize = parseFloat(style.fontSize);
    }
    if (style.color && style.color !== 'rgb(0, 0, 0)') {
      formatting.color = rgbToHex(style.color);
    }
    if (style.backgroundColor && style.backgroundColor !== 'rgba(0, 0, 0, 0)') {
      formatting.backgroundColor = rgbToHex(style.backgroundColor);
    }

    return formatting;
  };

  // Get inherited formatting from parent elements
  const getInheritedFormatting = (element) => {
    let formatting = {};
    let current = element;

    while (current && current !== editorRef.current) {
      const elementFormatting = getElementFormatting(current);
      formatting = { ...elementFormatting, ...formatting };
      current = current.parentElement;
    }

    return formatting;
  };

  // Get text alignment
  const getAlignment = (element) => {
    const style = window.getComputedStyle(element);
    return style.textAlign || 'left';
  };

  // Convert RGB to Hex
  const rgbToHex = (rgb) => {
    const result = rgb.match(/\d+/g);
    if (result) {
      const [r, g, b] = result.map(Number);
      return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
    }
    return '#000000';
  };

  // Execute formatting commands
  const execCommand = (command, value = null) => {
    document.execCommand(command, false, value);
    updateContent();
  };

  // Update content and RTF data
  const updateContent = () => {
    if (editorRef.current) {
      const html = editorRef.current.innerHTML;
      setContent(html);
      const rtfData = convertToRtfData(html);
      setRtfData(rtfData);
    }
  };

  // Handle editor input
  const handleInput = () => {
    updateContent();
  };

  // Insert link
  const insertLink = () => {
    const url = prompt('Enter URL:');
    if (url) {
      execCommand('createLink', url);
    }
  };

  // Send data to backend
  const sendToBackend = async () => {
    if (!rtfData) return;

    try {
      const response = await fetch('/api/document/rtf-content', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          rtfData: rtfData,
          documentId: 'sample-doc-id' // Replace with actual document ID
        })
      });

      if (response.ok) {
        console.log('RTF data sent successfully');
      }
    } catch (error) {
      console.error('Error sending RTF data:', error);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6 bg-white">
      <h2 className="text-2xl font-bold mb-6">Rich Text Editor - Word Compatible</h2>
      
      {/* Toolbar */}
      <div className="border border-gray-300 rounded-t-lg p-3 bg-gray-50 flex flex-wrap gap-2">
        <button
          onClick={() => execCommand('bold')}
          className="p-2 rounded hover:bg-gray-200 border"
          title="Bold"
        >
          <Bold size={16} />
        </button>
        
        <button
          onClick={() => execCommand('italic')}
          className="p-2 rounded hover:bg-gray-200 border"
          title="Italic"
        >
          <Italic size={16} />
        </button>
        
        <button
          onClick={() => execCommand('underline')}
          className="p-2 rounded hover:bg-gray-200 border"
          title="Underline"
        >
          <Underline size={16} />
        </button>

        <div className="w-px bg-gray-300 mx-2"></div>

        <button
          onClick={() => execCommand('justifyLeft')}
          className="p-2 rounded hover:bg-gray-200 border"
          title="Align Left"
        >
          <AlignLeft size={16} />
        </button>
        
        <button
          onClick={() => execCommand('justifyCenter')}
          className="p-2 rounded hover:bg-gray-200 border"
          title="Align Center"
        >
          <AlignCenter size={16} />
        </button>
        
        <button
          onClick={() => execCommand('justifyRight')}
          className="p-2 rounded hover:bg-gray-200 border"
          title="Align Right"
        >
          <AlignRight size={16} />
        </button>

        <div className="w-px bg-gray-300 mx-2"></div>

        <button
          onClick={() => execCommand('insertUnorderedList')}
          className="p-2 rounded hover:bg-gray-200 border"
          title="Bullet List"
        >
          <List size={16} />
        </button>
        
        <button
          onClick={() => execCommand('insertOrderedList')}
          className="p-2 rounded hover:bg-gray-200 border"
          title="Numbered List"
        >
          <ListOrdered size={16} />
        </button>

        <div className="w-px bg-gray-300 mx-2"></div>

        <select
          onChange={(e) => execCommand('formatBlock', e.target.value)}
          className="px-3 py-1 border rounded"
          defaultValue=""
        >
          <option value="">Normal</option>
          <option value="h1">Heading 1</option>
          <option value="h2">Heading 2</option>
          <option value="h3">Heading 3</option>
          <option value="h4">Heading 4</option>
        </select>

        <select
          onChange={(e) => execCommand('fontSize', e.target.value)}
          className="px-3 py-1 border rounded"
          defaultValue="3"
        >
          <option value="1">8pt</option>
          <option value="2">10pt</option>
          <option value="3">12pt</option>
          <option value="4">14pt</option>
          <option value="5">18pt</option>
          <option value="6">24pt</option>
          <option value="7">36pt</option>
        </select>

        <input
          type="color"
          onChange={(e) => execCommand('foreColor', e.target.value)}
          className="w-8 h-8 border rounded"
          title="Text Color"
        />

        <button
          onClick={insertLink}
          className="p-2 rounded hover:bg-gray-200 border"
          title="Insert Link"
        >
          <Link size={16} />
        </button>
      </div>

      {/* Editor */}
      <div
        ref={editorRef}
        contentEditable
        onInput={handleInput}
        className="min-h-96 p-4 border-l border-r border-b border-gray-300 focus:outline-none"
        style={{ fontSize: '12pt', lineHeight: '1.15' }}
        suppressContentEditableWarning={true}
      />

      {/* Actions */}
      <div className="mt-4 flex gap-4">
        <button
          onClick={updateContent}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Update RTF Data
        </button>
        
        <button
          onClick={sendToBackend}
          className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
          disabled={!rtfData}
        >
          Send to Backend
        </button>
      </div>

      {/* RTF Data Preview */}
      {rtfData && (
        <div className="mt-6">
          <h3 className="text-lg font-semibold mb-2">RTF Data Structure (Word Compatible)</h3>
          <pre className="bg-gray-100 p-4 rounded text-sm overflow-auto max-h-96">
            {JSON.stringify(rtfData, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};

export default RichTextEditor;