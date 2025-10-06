using System.Text;
using ParserModule.Nodes;

namespace ParserModule;

public sealed class AstPrinter : IAstNodeVisitor
{
    private readonly StringBuilder _sb = new();
    
    public void VisitIntegerNumberExpression(LiteralIntegerExpressionNode integerNumberExpression)
    {
        _sb.Append(integerNumberExpression.Value);
    }

    public void VisitBinaryExpression(BinaryExpressionNode binaryExpressionNode)
    {
        _sb.Append("(");
        binaryExpressionNode.Left.Accept(this);
        _sb.Append(binaryExpressionNode.Op.Lexeme);
        binaryExpressionNode.Right.Accept(this);       
        _sb.Append(")");       
    }

    public void VisitUnaryExpression(UnaryExpressionNode unaryExpressionNode)
    {
        _sb.Append(unaryExpressionNode.Operator.Lexeme);
        unaryExpressionNode.Right.Accept(this);       
    }

    public override string ToString()
    {
        return _sb.ToString();       
    }
}