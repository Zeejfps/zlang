using System.Text;

namespace SemanticAnalysisModule;

public class Scope
{
    public Scope? Parent { get; }
    private readonly Dictionary<string, Symbol> _symbols = new();
    private readonly List<Scope> _children = new();
    
    public Scope(Scope? parent)
    {
        Parent = parent;
        if (parent != null)
        {
            parent._children.Add(this);
        }
    }

    public bool TryDefine(Symbol sym)
    {
        return _symbols.TryAdd(sym.Name, sym);
    }

    public Symbol? Resolve(string name)
    {
        if (_symbols.TryGetValue(name, out var sym))
            return sym;
        return Parent?.Resolve(name);
    }

    public override string ToString()
    {
        var sb = new StringBuilder();

        var indent = "";
        PrintSymbols(this, sb, indent);
        
        return sb.ToString();
    }

    private void PrintSymbols(Scope scope, StringBuilder sb, string indent)
    {
        foreach (var (id, symbol) in scope._symbols)
        {
            sb.Append(indent);
            sb.Append(id);
            sb.Append(" = ");
            sb.Append(symbol);
            sb.AppendLine();
        }

        indent += " ";
        foreach (var child in scope._children)
        {
            PrintSymbols(child, sb, indent);
        }
    }
}