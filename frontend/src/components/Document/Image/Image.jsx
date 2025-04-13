import React, { useState } from 'react';

const Image = ({ image, onUpdate }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [caption, setCaption] = useState(image.caption);
  const [altText, setAltText] = useState(image.alt);
  
  const handleSave = () => {
    setIsEditing(false);
    onUpdate({
      ...image,
      caption: caption,
      alt: altText
    });
  };
  
  const handleImageUpload = (e) => {
    // In a real implementation, this would handle file uploads
    // For now, we'll just simulate it
    console.log('Image upload triggered');
  };
  
  return (
    <div className="image-container">
      {isEditing ? (
        <div className="image-edit">
          <div className="image-upload">
            <label>
              Upload Image:
              <input type="file" accept="image/*" onChange={handleImageUpload} />
            </label>
          </div>
          <div className="image-fields">
            <label>
              Caption:
              <input
                type="text"
                value={caption}
                onChange={(e) => setCaption(e.target.value)}
              />
            </label>
            <label>
              Alt Text:
              <input
                type="text"
                value={altText}
                onChange={(e) => setAltText(e.target.value)}
              />
            </label>
          </div>
          <button onClick={handleSave}>Save</button>
        </div>
      ) : (
        <div onClick={() => setIsEditing(true)}>
          <figure className="image-figure">
            <img src={image.src} alt={image.alt} className="document-image" />
            <figcaption className="image-caption">{image.caption}</figcaption>
          </figure>
        </div>
      )}
    </div>
  );
};

export default Image;