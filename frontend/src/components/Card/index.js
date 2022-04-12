import './Card.css'

const Card = ({ title, children, className= '' }) => {
  return (
    <div className={`card ${className}`}>
      <h1 className='cardHeader'>{title}</h1>
      {children}
    </div>
  );
}

export default Card;
