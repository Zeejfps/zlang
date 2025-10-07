using System.Text;
using ParserModule.Nodes;

namespace ParserModule;

public sealed class AstPrinter : IAstNodeVisitor
{
    private readonly StringBuilder _sb = new();
    
    public void VisitIntegerNumberExpression(LiteralIntegerExpressionNode integerNumberExpression)
    {
        _sb.Append(integerNumberExpression.Token.Lexeme);
    }

    public void VisitLiteralBoolExpression(LiteralBoolExpressionNode literalBoolExpressionNode)
    {
        _sb.Append(literalBoolExpressionNode.Token.Lexeme);       
    }

    public void VisitBinaryExpression(BinaryExpressionNode binaryExpressionNode)
    {
        _sb.Append('(');
        binaryExpressionNode.Left.Accept(this);
        _sb.Append(binaryExpressionNode.Op.Lexeme);
        binaryExpressionNode.Right.Accept(this);       
        _sb.Append(')');       
    }

    public void VisitUnaryExpression(UnaryExpressionNode unaryExpressionNode)
    {
        _sb.Append(unaryExpressionNode.Operator.Lexeme);
        unaryExpressionNode.Right.Accept(this);       
    }

    public void VisitIdentifierExpression(IdentifierExpressionNode identifierExpressionNode)
    {
        _sb.Append(identifierExpressionNode.Token.Lexeme);
    }

    public void VisitVarAssignmentStatement(VarAssignmentStatementNode node)
    {
        _sb.Append(node.Name);
        if (node.Type != null)
        {
            _sb.Append(':');
            _sb.Append(' ');
            node.Type.Accept(this);
        }
        _sb.Append(' ');
        _sb.Append('=');
        _sb.Append(' ');
        node.Value.Accept(this);
    }

    public void VisitNamedTypeNode(NamedTypeNode namedTypeNode)
    {
        _sb.Append(namedTypeNode.Name);
    }

    public override string ToString()
    {
        return _sb.ToString();       
    }
}