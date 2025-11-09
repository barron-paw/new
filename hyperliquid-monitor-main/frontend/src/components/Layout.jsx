import './Layout.css';

export function Layout({ header, actions, children, footer }) {
  return (
    <div className="layout">
      <header className="layout__header">
        <div className="layout__header-inner">
          <div className="layout__header-content">{header}</div>
          {actions ? <div className="layout__header-actions">{actions}</div> : null}
        </div>
      </header>
      <main className="layout__main">{children}</main>
      {footer ? <footer className="layout__footer">{footer}</footer> : null}
    </div>
  );
}

export default Layout;
