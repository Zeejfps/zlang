using System.Text;
using ParserModule.Nodes;

namespace ParserModule;

public sealed class AstPrinter : IAstNodeVisitor
{
    private readonly StringBuilder _sb = new();
    
    public void VisitIntegerNumberExpression(LiteralIntegerExpression integerNumberExpression)
    {
        _sb.Append(integerNumberExpression.Value);
    }

    public override string ToString()
    {
        return _sb.ToString();       
    }
}